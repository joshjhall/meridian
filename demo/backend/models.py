"""Shared data contracts for the demo.

These Pydantic models are the only schema: the API, the Jinja templates and
the LangGraph pipeline all use them directly. Don't define a local claim,
event or audit shape elsewhere.

Skill, Tier and Stage are enums: code that needs "all tiers" iterates the enum
rather than listing members, so adding a tier (e.g. T4, T5) means editing this
file only.
"""

from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

SLA_HOURS = 24
SLA_AT_RISK_HOURS = 6  # amber under 6h left (panel_examples.md, Header)


class Skill(StrEnum):
    COLLISION = "Collision"
    COMPREHENSIVE = "Comprehensive"
    BODILY_INJURY = "Bodily Injury"
    PROPERTY_DAMAGE = "Property Damage"
    LIABILITY = "Liability"


class Tier(StrEnum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


TIER_LABELS: dict[Tier, str] = {
    Tier.T1: "standard",
    Tier.T2: "involved",
    Tier.T3: "senior",
}


class Stage(StrEnum):
    RECEIVED = "received"
    VALIDATED = "validated"
    ENRICHED = "enriched"
    PRIORITIZED = "prioritized"
    ASSIGNED = "assigned"
    WITH_ADJUSTER = "with_adjuster"
    EXCEPTION = "exception"


class ExceptionReason(StrEnum):
    """Why a claim failed safe into the exceptions lane to wait for a person."""

    MISSING_FIELDS = "missing_fields"
    OCR_CONFLICT = "ocr_conflict"
    UNKNOWN_RULE = "unknown_rule"
    FAILED_WRITE = "failed_write"
    LLM_FALLBACK = "llm_fallback"


EXCEPTION_LABELS: dict[ExceptionReason, str] = {
    ExceptionReason.MISSING_FIELDS: "Missing fields",
    ExceptionReason.OCR_CONFLICT: "OCR conflicts with EDI",
    ExceptionReason.UNKNOWN_RULE: "No routing rule matched",
    ExceptionReason.FAILED_WRITE: "ClaimsPro write failed",
    ExceptionReason.LLM_FALLBACK: "LLM unavailable, fell back",
}


YesNo = Literal["Yes", "No"]
IntakeChannel = Literal["E-Portal", "Phone", "Fax/EDI"]
Complexity = Literal["Simple", "Moderate", "Complex"]
Disposition = Literal["Paid in Full", "Partial Payment", "Denied", "Settled", "Pending Review"]
ReviewLane = Literal["fast_lane", "standard_review", "regulatory_review", "senior_review"]
BriefStatus = Literal["pending", "ready", "failed"]
AdjusterRole = Literal["adjuster", "senior", "lead"]
SlaState = Literal["on_track", "at_risk", "breached"]
# A reliable write's progress (pipeline events) and its outcome stored on the claim.
WriteStatus = Literal["pending", "retrying", "confirmed", "failed"]
ClaimWriteStatus = Literal["pending", "confirmed", "write_failed"]


class Claim(BaseModel):
    # Extract columns, in reference/data_dictionary.md order.
    claim_id: str = Field(pattern=r"^IS-CLM-\d{10}$")
    filed_date: date
    claim_type: Skill
    state: str = Field(min_length=2, max_length=2)
    intake_channel: IntakeChannel
    cost_per_claim_usd: float
    claim_amount_usd: float
    complexity: Complexity
    automation_eligibility_score: int
    flagged_for_human_review: YesNo
    requires_human_by_regulation: YesNo
    queue_wait_hours: float
    handling_hours: float
    total_cycle_time_hours: float
    disposition: Disposition
    denial_reason: str | None = None
    adjuster_id: str = Field(pattern=r"^ADJ-\d{3}$")
    document_count: int
    customer_satisfaction_1to5: float | None = None
    review_actually_needed: YesNo | None = None

    # Demo provenance.
    received_at: datetime
    synthetic: bool = False
    sources: list[str] = []
    details: dict[str, Any] = {}

    # ClaimsPro custom fields, filled by the pre-processing pipeline (#3).
    skills: list[Skill] = []
    tier: Tier | None = None
    routing_reason: str | None = None
    review_lane: ReviewLane | None = None
    brief_status: BriefStatus | None = None
    # Outcome of the latest reliable write (#2); "pending" means not yet saved.
    write_status: ClaimWriteStatus | None = None

    @computed_field  # type: ignore[prop-decorator]  # Pydantic's documented pattern
    @property
    def sla_due_at(self) -> datetime:
        return self.received_at + timedelta(hours=SLA_HOURS)

    def sla_state(self, now: datetime) -> SlaState:
        """Pass clock.now(), not the wall clock."""
        left = self.sla_due_at - now
        if left <= timedelta(0):
            return "breached"
        if left < timedelta(hours=SLA_AT_RISK_HOURS):
            return "at_risk"
        return "on_track"


class FixtureExpectation(BaseModel):
    """What docs/presentation/panel_examples.md says the pipeline should produce."""

    skills: list[Skill]
    tier: Tier
    regulated: bool
    routing_reason: str
    sla_in_demo: SlaState


class ClaimFixture(BaseModel):
    claim: Claim
    expected: FixtureExpectation


class Adjuster(BaseModel):
    id: str = Field(pattern=r"^ADJ-\d{3}$")
    name: str
    skills: list[Skill] = Field(min_length=1)
    tiers: list[Tier] = Field(min_length=1)
    role: AdjusterRole
    current_load: int = Field(ge=0)
    extract_code: bool


class PipelineEvent(BaseModel):
    claim_id: str
    stage: Stage
    timestamp: datetime
    payload: dict[str, Any] = {}
    pipeline_version: str


class ClaimNote(BaseModel):
    text: str
    author: str
    idempotency_key: str
    at: datetime


class Alert(BaseModel):
    """Raised when a ClaimsPro write still fails after every retry."""

    claim_id: str
    operation: str
    idempotency_key: str
    recipients: list[str]
    message: str
    raised_at: datetime


class ReviewInterval(BaseModel):
    actor: str
    start: datetime
    end: datetime | None = None


class AuditRecord(BaseModel):
    # The five fields the compliance floor requires.
    claim_id: str
    input_data_ref: str
    model_version: str
    output: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    human_reviewed: bool
    # Beyond the floor.
    rationale: str
    skills: list[Skill] = []
    tier: Tier | None = None
    review_intervals: list[ReviewInterval] = []


# Panel summary: the six sections in docs/presentation/panel_examples.md.


class SourceRef(BaseModel):
    label: str
    path: str
    anchor: str | None = None
    verified: bool = True


class PanelHeader(BaseModel):
    claim_id: str
    skills: list[Skill]
    tier: Tier
    sla_due_at: datetime
    regulated: bool
    routing_reason: str


class WhatMattersPoint(BaseModel):
    text: str
    unusual: bool = False
    source: SourceRef


class KeyFact(BaseModel):
    label: str
    value: str
    sources: list[SourceRef] = []


class KeyFacts(BaseModel):
    template: Skill
    facts: list[KeyFact]
    collapsed: bool = True


class AttentionItem(BaseModel):
    kind: Literal["missing", "conflict", "low_confidence"]
    label: str
    sources: list[SourceRef] = []
    values: list[str] = []
    suggested: str | None = None


class ContentsEntry(BaseModel):
    fact: str
    location: SourceRef


class FooterTouch(BaseModel):
    actor: str
    at: datetime


class PanelFooter(BaseModel):
    touches: list[FooterTouch] = []
    pipeline_version: str


class PanelSummary(BaseModel):
    header: PanelHeader
    what_matters: list[WhatMattersPoint] = Field(max_length=4)
    key_facts: KeyFacts
    needs_attention: list[AttentionItem] = []
    contents: list[ContentsEntry] = []
    footer: PanelFooter


# --- Learning-loop history (admin view, #8) ---


class HistoryPoint(BaseModel):
    week: int  # weeks since kickoff
    value: float


class HistorySeries(BaseModel):
    key: str
    label: str
    unit: str
    mark: Literal["line", "bar"]
    source: str  # where the week-0 value comes from
    target: float
    target_label: str
    points: list[HistoryPoint]


class HistoryChart(BaseModel):
    """One chart with two series on independent y-axes (left: primary)."""

    id: str
    title: str
    subtitle: str
    primary: HistorySeries
    secondary: HistorySeries


class Release(BaseModel):
    week: int
    version: str
    kind: Literal["release", "rollback"]
    charts: list[str]  # HistoryChart ids the flag appears on
    notes: str


class LearningHistory(BaseModel):
    caption: str
    charts: list[HistoryChart]
    releases: list[Release]
