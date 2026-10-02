"""Admin queues board (#7): every adjuster's open work, and manual moves between queues.

A move is a `TransferWorkItem` through the reliable-write wrapper (#2). The route
validates it here first, so a blocked move never reaches ClaimsPro.
"""

import threading
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from typing import Any

import monitor

from claimspro_sim import ClaimsProSim, reliable_write
from claimspro_sim.faults import SoapOperation
from claimspro_sim.store import seed_claims
from fixtures import load_claim_fixtures, load_roster
from models import TIER_LABELS, Adjuster, Claim, SlaState, Tier

TRANSFER: SoapOperation = "TransferWorkItem"
MAX_ATTEMPTS = 3
REVIEW_ROLES = {"senior", "lead"}  # who may take a regulated T3 claim

Runner = Callable[[Callable[[], Any]], None]


def run_in_thread(job: Callable[[], Any]) -> None:
    # reliable_write blocks for its verify reads and backoff; the board polls for the outcome.
    threading.Thread(target=job, daemon=True).start()


def is_regulated(claim: Claim) -> bool:
    # TODO(#3): switch to pipeline.rules.regulatory_check once #3 merges, and drop this copy.
    return claim.requires_human_by_regulation == "Yes" or (
        claim.state in monitor.REGULATED_STATES
        and claim.claim_amount_usd > monitor.REGULATED_OVER_USD
    )


def claim_tier(claim: Claim) -> Tier | None:
    """The pipeline's tier (#3), or the fixture's expected tier until the pipeline fills it."""
    if claim.tier is not None:
        return claim.tier
    fixture = load_claim_fixtures().get(claim.claim_id)
    return fixture.expected.tier if fixture else None


def review_tier(claim: Claim) -> Tier:
    # A regulated claim with no tier yet is held to the strictest lane, never a looser one.
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
    if not is_regulated(claim):
        return None
    # Mirrors #3's routing: regulated work goes to the review lane of an adjuster
    # holding the claim's tier; T3 review is senior or lead only.
    tier = review_tier(claim)
    if tier not in target.tiers:
        return f"Regulated claim needs human review: {target.name} has no {tier} review lane."
    if tier is Tier.T3 and target.role not in REVIEW_ROLES:
        return f"Regulated {tier} claim needs a senior or lead reviewer; {target.name} is not."
    return None


def start_transfer(
    sim: ClaimsProSim, claim_id: str, to_adjuster_id: str, run: Runner = run_in_thread
) -> str:
    """Send the move to ClaimsPro in the background. Returns the key to poll its status by."""
    key = str(uuid.uuid4())
    run(
        lambda: reliable_write(
            sim,
            TRANSFER,
            claim_id,
            {"to_adjuster_id": to_adjuster_id},
            idempotency_key=key,
            max_attempts=MAX_ATTEMPTS,
        )
    )
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
    regulated: bool
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


@cache
def _seeded_counts() -> Counter[str]:
    return Counter(c.adjuster_id for c in seed_claims())


def load_for(adjuster: Adjuster, open_here: int) -> int:
    # The roster's load covers all of an adjuster's work; the simulator holds a
    # sample of it, so moves shift the roster figure by the net change here.
    return max(0, adjuster.current_load + open_here - _seeded_counts()[adjuster.id])


def queue_claim(claim: Claim, now: datetime) -> QueueClaim:
    return QueueClaim(
        claim=claim,
        regulated=is_regulated(claim),
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
            Queue(adjuster, load_for(adjuster, len(claims)), claims)
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
