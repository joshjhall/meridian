"""Fixture event feed and state for the admin pipeline monitor (#6).

Until the replay runner (#5) streams real pipeline events, the monitor plays a
deterministic script: the six fixture claims plus seeded background traffic.
Everything here speaks `PipelineEvent`, so switching to the live stream means
feeding the same `MonitorState` from `/api/events` instead of `fixture_script`.

Each event's payload carries what that stage learned (skills at enrichment,
tier and review lane at prioritization, and so on), so a card fills in as its
claim moves right. An exception event carries `reason` and, for source
conflicts, a `conflicts` list naming each field and what each source says.
"""

import asyncio
import json
import random
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache
from typing import Any

from fixtures import load_claim_fixtures, load_roster
from models import EXCEPTION_LABELS, ExceptionReason, PipelineEvent, Skill, Stage, Tier

PIPELINE_VERSION = "routing-v0.4.0"

# The lanes, left to right. The exceptions lane sits apart from the flow.
LANES: list[Stage] = [s for s in Stage if s is not Stage.EXCEPTION]

# The situation each fixture claim demonstrates, per panel_examples.md "Variety at a glance".
STORIES: dict[str, str] = {
    "IS-CLM-2025000300": "Clean",
    "IS-CLM-2025004222": "Hard judgment",
    "IS-CLM-2025002993": "Messy intake",
    "IS-CLM-2025000375": "Regulatory gap",
    "IS-CLM-2025004518": "Disputed fault",
    "IS-CLM-2025002043": "Thin file",
}

# Named states from the compliance floor; the other four aren't named in discovery.
REGULATED_STATES = {"CA", "NY", "NJ", "FL", "IL", "PA", "OH", "GA"}
REGULATED_OVER_USD = 10_000

# Claim 2993's source conflicts, from docs/presentation/panel_examples.md (claim 3).
CONFLICTS_2993: list[dict[str, str]] = [
    {"field": "Policy number", "ocr": "CA-CA-88l23-l8", "edi": "CA-CA-88123-18"},
    {"field": "Bumper line", "ocr": "1,B00.00", "edi": "1,800.00 (from line-item recap)"},
    {"field": "Date of loss", "ocr": "O9/O____ (cut off)", "edi": "2025-09-08 (= fax receipt)"},
    {"field": "Claimant contact", "ocr": "blank", "edi": "blank"},
]

REVIEW_LANES = {"regulatory_review", "senior_review"}

START = datetime(2025, 9, 8, 9, 0)
CLAIM_GAP_S = 1.6  # seconds between claims entering the feed
STEP_S = 2.2  # seconds a claim spends per stage, before jitter
HOLD_S = 8.0  # pause at the end of the script before it loops


@dataclass(frozen=True)
class Scheduled:
    at: float  # seconds from the start of the script, at speed 1
    event: PipelineEvent


@dataclass
class _Spec:
    claim_id: str
    state: str
    channel: str
    amount: float
    skills: list[Skill]
    tier: Tier
    sla: str
    routing_reason: str
    exception: tuple[Stage, ExceptionReason, list[dict[str, str]]] | None = None
    recovers: bool = False  # leaves the exceptions lane after a retry

    @property
    def regulated(self) -> bool:
        return self.state in REGULATED_STATES and self.amount > REGULATED_OVER_USD

    @property
    def review_lane(self) -> str:
        if self.tier is Tier.T3:
            return "senior_review"
        if self.regulated:
            return "regulatory_review"
        return "fast_lane" if self.tier is Tier.T1 else "standard_review"


def _fixture_specs() -> list[_Spec]:
    specs = []
    for claim_id, fx in load_claim_fixtures().items():
        c, e = fx.claim, fx.expected
        spec = _Spec(
            claim_id=claim_id,
            state=c.state,
            channel=c.intake_channel,
            amount=c.claim_amount_usd,
            skills=e.skills,
            tier=e.tier,
            sla=e.sla_in_demo,
            routing_reason=e.routing_reason,
        )
        if claim_id == "IS-CLM-2025002993":
            spec.exception = (Stage.VALIDATED, ExceptionReason.OCR_CONFLICT, CONFLICTS_2993)
        specs.append(spec)
    return specs


def _background_specs(rng: random.Random, n: int) -> list[_Spec]:
    states = [*sorted(REGULATED_STATES), "TX", "AZ", "WA", "CO", "NC", "MI", "TN"]
    channels = ["E-Portal", "E-Portal", "Phone", "Fax/EDI"]
    taken = set(load_claim_fixtures())
    specs = []
    while len(specs) < n:
        claim_id = f"IS-CLM-2025{rng.randrange(5000, 1_000_000):06d}"
        if claim_id in taken:
            continue
        taken.add(claim_id)
        skills = rng.sample(list(Skill), k=rng.choice([1, 1, 1, 2]))
        tier = rng.choices(list(Tier), weights=[5, 3, 1])[0]
        amount = round(rng.lognormvariate(8.6, 0.9), 2)
        specs.append(
            _Spec(
                claim_id=claim_id,
                state=rng.choice(states),
                channel=rng.choice(channels),
                amount=amount,
                skills=skills,
                tier=tier,
                sla=rng.choices(["on_track", "at_risk", "breached"], weights=[8, 2, 1])[0],
                routing_reason=f"{', '.join(skills)} → {tier} by rule",
            )
        )
    # A few background claims fail safe too, so the lane shows more than one reason.
    specs[4].exception = (Stage.ASSIGNED, ExceptionReason.FAILED_WRITE, [])
    specs[4].recovers = True
    specs[9].exception = (Stage.ENRICHED, ExceptionReason.LLM_FALLBACK, [])
    specs[13].exception = (Stage.VALIDATED, ExceptionReason.MISSING_FIELDS, [])
    specs[13].channel = "Fax/EDI"
    return specs


def _adjuster_for(spec: _Spec, rng: random.Random) -> str:
    fits = [a for a in load_roster() if spec.tier in a.tiers and set(spec.skills) <= set(a.skills)]
    pick = min(fits, key=lambda a: (a.current_load, rng.random())) if fits else None
    return f"{pick.name} ({pick.id})" if pick else "unassigned"


def _payload(stage: Stage, spec: _Spec, rng: random.Random) -> dict[str, Any]:
    match stage:
        case Stage.RECEIVED:
            return {"state": spec.state, "channel": spec.channel, "amount": spec.amount}
        case Stage.VALIDATED:
            return {"fields_complete": True}
        case Stage.ENRICHED:
            return {"skills": [str(s) for s in spec.skills]}
        case Stage.PRIORITIZED:
            return {
                "tier": str(spec.tier),
                "regulated": spec.regulated,
                "review_lane": spec.review_lane,
                "sla": spec.sla,
                "routing_reason": spec.routing_reason,
            }
        case Stage.ASSIGNED:
            return {"adjuster": _adjuster_for(spec, rng)}
        case _:
            return {}


def _events_for(spec: _Spec, t0: float, rng: random.Random) -> list[Scheduled]:
    out: list[Scheduled] = []
    t = t0

    def emit(stage: Stage, payload: dict[str, Any]) -> None:
        ts = START + timedelta(seconds=round(t * 60))  # one demo second = one minute
        event = PipelineEvent(
            claim_id=spec.claim_id,
            stage=stage,
            timestamp=ts,
            payload=payload,
            pipeline_version=PIPELINE_VERSION,
        )
        out.append(Scheduled(round(t, 2), event))

    for stage in LANES:
        if spec.exception and spec.exception[0] is stage:
            _, reason, conflicts = spec.exception
            emit(Stage.EXCEPTION, {"reason": str(reason), "conflicts": conflicts})
            if not spec.recovers:
                return out
            t += STEP_S * 3  # waits for a person, then the write is retried
            emit(stage, {**_payload(stage, spec, rng), "retried": True})
        else:
            emit(stage, _payload(stage, spec, rng))
        t += STEP_S * rng.uniform(0.7, 1.4)
    return out


@cache
def fixture_script(seed: int = 6, background: int = 18) -> tuple[Scheduled, ...]:
    """The deterministic demo feed, ordered by time."""
    rng = random.Random(seed)
    fixtures = _fixture_specs()
    queue = _background_specs(rng, background)
    # Spread the six demo claims through the first part of the feed.
    for i, spec in enumerate(fixtures):
        queue.insert(i * 3, spec)
    events = [e for i, spec in enumerate(queue) for e in _events_for(spec, i * CLAIM_GAP_S, rng)]
    return tuple(sorted(events, key=lambda s: s.at))


@dataclass
class ClaimView:
    """What the monitor knows about one claim: payloads merged as stages arrive."""

    claim_id: str
    stage: Stage
    pinned: bool
    story: str | None
    facts: dict[str, Any] = field(default_factory=dict)
    trace: list[PipelineEvent] = field(default_factory=list)

    @property
    def reason_label(self) -> str | None:
        reason = self.facts.get("reason")
        return EXCEPTION_LABELS[ExceptionReason(reason)] if reason else None


@dataclass
class MonitorState:
    claims: dict[str, ClaimView] = field(default_factory=dict)
    routed_to_review: set[str] = field(default_factory=set)

    def apply(self, event: PipelineEvent) -> ClaimView:
        view = self.claims.get(event.claim_id)
        if view is None:
            view = ClaimView(
                claim_id=event.claim_id,
                stage=event.stage,
                pinned=event.claim_id in STORIES,
                story=STORIES.get(event.claim_id),
            )
            self.claims[event.claim_id] = view
        view.stage = event.stage
        view.trace.append(event)
        if event.stage is not Stage.EXCEPTION:
            view.facts.pop("reason", None)
            view.facts.pop("conflicts", None)
        view.facts.update(event.payload)
        if view.facts.get("regulated") and view.facts.get("review_lane") in REVIEW_LANES:
            self.routed_to_review.add(event.claim_id)
        return view

    @property
    def open_exceptions(self) -> int:
        return sum(v.stage is Stage.EXCEPTION for v in self.claims.values())

    def counters(self) -> dict[str, int]:
        return {"routed": len(self.routed_to_review), "exceptions": self.open_exceptions}


def replay(events: tuple[Scheduled, ...] | None = None) -> MonitorState:
    """Fold the whole script (or a prefix of it) into a state."""
    state = MonitorState()
    for s in events if events is not None else fixture_script():
        state.apply(s.event)
    return state


def _frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def event_stream(
    render_card: Callable[[ClaimView], str],
    speed: float = 1.0,
    limit: int | None = None,
) -> AsyncIterator[str]:
    """Server-sent events for the monitor: one `claim` frame per pipeline event.

    Loops the script forever (sending a `reset` frame between passes) unless
    `limit` caps the number of claim frames, which tests use.
    """
    sent = 0
    while True:
        state = MonitorState()
        clock = 0.0
        for s in fixture_script():
            await asyncio.sleep(max(0.0, s.at - clock) / speed)
            clock = s.at
            view = state.apply(s.event)
            yield _frame(
                "claim",
                {
                    "claim_id": view.claim_id,
                    "stage": str(view.stage),
                    "html": render_card(view),
                    "counters": state.counters(),
                },
            )
            sent += 1
            if limit is not None and sent >= limit:
                return
        await asyncio.sleep(HOLD_S / speed)
        yield _frame("reset", {"counters": MonitorState().counters()})
