"""Admin queues board (#7): every adjuster's open work, and manual moves between queues.

A move is a `TransferWorkItem` through the reliable-write wrapper (#2). The route
validates it here first, so a blocked move never reaches ClaimsPro.
"""

import threading
import uuid
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from claimspro_sim import ClaimsProSim, reliable_write
from claimspro_sim.faults import SoapOperation
from claimspro_sim.reliable import SIM_VERSION
from fixtures import load_claim_fixtures, load_roster
from models import TIER_LABELS, Adjuster, Claim, PipelineEvent, SlaState, Stage, Tier
from pipeline.assign import SENIOR_ROLES
from pipeline.rules import regulatory_check

TRANSFER: SoapOperation = "TransferWorkItem"
MAX_ATTEMPTS = 3

Runner = Callable[[Callable[[], Any]], None]


def run_in_thread(job: Callable[[], Any]) -> None:
    # reliable_write blocks for its verify reads and backoff; the board polls for the outcome.
    threading.Thread(target=job, daemon=True).start()


def transfer_fault_on(sim: ClaimsProSim) -> bool:
    config = sim.faults.configs().get(TRANSFER)
    return config is not None and config.failure_rate > 0


def sentence(text: str) -> str:
    """First letter up, the rest untouched (str.capitalize would lower "GA" and "$10K")."""
    return text[:1].upper() + text[1:]


def needs_review(claim: Claim) -> bool:
    """The pipeline's rule (#3): regulated by label or state rule, or flagged for review."""
    return regulatory_check(claim).review_required


def claim_tier(claim: Claim) -> Tier | None:
    """The pipeline's tier (#3), or the fixture's expected tier until the pipeline fills it."""
    if claim.tier is not None:
        return claim.tier
    fixture = load_claim_fixtures().get(claim.claim_id)
    return fixture.expected.tier if fixture else None


def review_tier(claim: Claim) -> Tier:
    # A claim needing review with no tier yet is held to the strictest lane, never a looser one.
    return claim_tier(claim) or list(Tier)[-1]


def top_tier(adjuster: Adjuster) -> Tier:
    return max(adjuster.tiers, key=list(Tier).index)


def block_reason(claim: Claim, target: Adjuster | None) -> str | None:
    """Why this move can't go to ClaimsPro, or None when it can."""
    if target is None:
        return "Unknown adjuster."
    if target.id == claim.adjuster_id:
        return f"Already in {target.name}'s queue."
    if claim.write_status == "pending":
        return f"A ClaimsPro write for {claim.claim_id} is still in flight."
    regulation = regulatory_check(claim)
    if not regulation.review_required:
        return None
    # Same eligibility as the pipeline's assign.match: the adjuster holds the claim's
    # tier, and senior review (every T3 claim) is senior or lead only.
    tier = review_tier(claim)
    why = sentence(regulation.reason or "needs review")
    if tier not in target.tiers:
        return f"{why}: {target.name} has no {tier} review lane."
    if tier is Tier.T3 and target.role not in SENIOR_ROLES:
        return f"{why}: {tier} needs a senior or lead reviewer; {target.name} is not."
    return None


class TransferBlocked(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Claims with a move not yet settled, per simulator; weak so a discarded sim takes its set along.
_in_flight: weakref.WeakKeyDictionary[ClaimsProSim, set[str]] = weakref.WeakKeyDictionary()
_in_flight_lock = threading.Lock()


def start_transfer(
    sim: ClaimsProSim, claim_id: str, target: Adjuster | None, run: Runner = run_in_thread
) -> str:
    """Check the move and send it to ClaimsPro in the background, or raise TransferBlocked.

    Returns the key to poll its status by. The check and the in-flight mark happen
    under one lock, so two quick drops of the same claim can't both go out.
    """
    with _in_flight_lock:
        busy = _in_flight.setdefault(sim, set())
        claim = sim.store.get(claim_id)
        if claim is None:
            raise KeyError(claim_id)
        reason = (
            "A ClaimsPro write for this claim is still in flight." if claim_id in busy else None
        )
        reason = reason or block_reason(claim, target)
        if reason is not None or target is None:
            raise TransferBlocked(reason or "Unknown adjuster.")
        busy.add(claim_id)

    key = str(uuid.uuid4())
    to_adjuster_id = target.id

    def job() -> None:
        try:
            reliable_write(
                sim,
                TRANSFER,
                claim_id,
                {"to_adjuster_id": to_adjuster_id},
                idempotency_key=key,
                max_attempts=MAX_ATTEMPTS,
            )
        except Exception as e:
            # reliable_write rejects some requests before its first event; without one
            # for this key the board would poll "pending" forever.
            if not any(ev.payload.get("idempotency_key") == key for ev in sim.events(claim_id)):
                sim.record_event(
                    PipelineEvent(
                        claim_id=claim_id,
                        stage=Stage.ASSIGNED,
                        timestamp=sim.now(),
                        pipeline_version=SIM_VERSION,
                        payload={
                            "operation": TRANSFER,
                            "write_status": "failed",
                            "attempt": 0,
                            "idempotency_key": key,
                            "reason": f"rejected before sending: {e}",
                        },
                    )
                )
            raise
        finally:
            with _in_flight_lock:
                busy.discard(claim_id)

    try:
        run(job)
    except BaseException:
        with _in_flight_lock:
            busy.discard(claim_id)
        raise
    return key


def write_progress(sim: ClaimsProSim, claim_id: str, key: str) -> dict[str, Any]:
    """The latest write-status payload for one move; pending until its first event lands."""
    for event in reversed(sim.events(claim_id)):
        if event.payload.get("idempotency_key") == key:
            return event.payload
    return {"write_status": "pending", "attempt": 1}


# --- The board ---


@dataclass
class QueueClaim:
    claim: Claim
    needs_review: bool
    review_reason: str | None
    tier: Tier | None
    review_tier: Tier
    sla: SlaState
    left: timedelta


@dataclass
class Queue:
    adjuster: Adjuster
    load: int
    claims: list[QueueClaim]


@dataclass
class TierGroup:
    tier: Tier
    label: str
    queues: list[Queue]


def queue_claim(claim: Claim, now: datetime) -> QueueClaim:
    regulation = regulatory_check(claim)
    return QueueClaim(
        claim=claim,
        needs_review=regulation.review_required,
        review_reason=regulation.reason,
        tier=claim_tier(claim),
        review_tier=review_tier(claim),
        sla=claim.sla_state(now),
        left=claim.sla_due_at - now,
    )


def board(sim: ClaimsProSim, now: datetime) -> list[TierGroup]:
    """Adjusters grouped by their highest tier, senior first; claims by SLA time left."""
    by_adjuster: dict[str, list[QueueClaim]] = {}
    for claim in sim.store.list_claims():
        by_adjuster.setdefault(claim.adjuster_id, []).append(queue_claim(claim, now))

    groups = {tier: TierGroup(tier, TIER_LABELS[tier], []) for tier in reversed(Tier)}
    for adjuster in sorted(load_roster(), key=lambda a: a.id):
        claims = sorted(by_adjuster.get(adjuster.id, []), key=lambda q: q.left)
        groups[top_tier(adjuster)].queues.append(
            # Load is the open claims in this queue: the badge always matches the
            # cards, and the roster's current_load is this same count at seed time.
            Queue(adjuster, len(claims), claims)
        )
    return [g for g in groups.values() if g.queues]


def roster_by_id() -> dict[str, Adjuster]:
    return {a.id: a for a in load_roster()}


def format_left(left: timedelta) -> str:
    """'5h 20m left', or how long ago the SLA passed."""
    minutes = abs(int(left.total_seconds())) // 60
    days, rem = divmod(minutes, 24 * 60)
    hours, mins = divmod(rem, 60)
    span = f"{days}d {hours}h" if days else f"{hours}h {mins}m"
    return f"{span} left" if left > timedelta(0) else f"breached {span} ago"
