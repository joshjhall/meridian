"""Board state for the admin pipeline monitor (#6).

The replay runner (#5) feeds every `PipelineEvent` from the real pipeline into a
`MonitorState`; each card is a `ClaimView` whose facts fill in as its claim moves
right. Each event's payload carries what that stage learned (skills at enrichment,
tier and review lane at prioritization, and so on). An exception event carries
`reason` and `issues`.
"""

from dataclasses import dataclass, field
from typing import Any

from models import EXCEPTION_LABELS, ExceptionReason, PipelineEvent, Stage

# The lanes, left to right. The exceptions lane sits apart from the flow.
LANES: list[Stage] = [s for s in Stage if s is not Stage.EXCEPTION]

# Column headings: what is happening to the claims in a lane now. The stage values
# stay past tense; they name events in the trace and the audit record.
LANE_LABELS: dict[Stage, str] = {
    Stage.RECEIVED: "Received",
    Stage.VALIDATED: "Validating",
    Stage.ENRICHED: "Enriching",
    Stage.PRIORITIZED: "Prioritizing",
    Stage.ASSIGNED: "Assigning",
    Stage.WITH_ADJUSTER: "With adjuster",
    Stage.EXCEPTION: "Requires manual review",
}

# The situation each fixture claim demonstrates, per panel_examples.md "Variety at a glance".
STORIES: dict[str, str] = {
    "IS-CLM-2025000300": "Clean",
    "IS-CLM-2025004222": "Hard judgment",
    "IS-CLM-2025002993": "Messy intake",
    "IS-CLM-2025000375": "Regulatory gap",
    "IS-CLM-2025004518": "Disputed fault",
    "IS-CLM-2025002043": "Thin file",
}

# What the "routed to review" counter counts: the lanes a regulated claim must reach.
REVIEW_LANES = {"regulatory_review", "senior_review"}


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
            for key in ("reason", "conflicts", "issues"):
                view.facts.pop(key, None)
        view.facts.update(event.payload)
        if view.facts.get("regulated") and view.facts.get("review_lane") in REVIEW_LANES:
            self.routed_to_review.add(event.claim_id)
        return view

    @property
    def open_exceptions(self) -> int:
        return sum(v.stage is Stage.EXCEPTION for v in self.claims.values())

    def counters(self) -> dict[str, int]:
        return {"routed": len(self.routed_to_review), "exceptions": self.open_exceptions}
