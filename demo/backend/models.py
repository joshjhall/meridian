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

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
IntakeStatus = Literal["complete"]
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
    # Set when a person confirms a fast-lane claim's intake from the panel.
    intake_status: IntakeStatus | None = None
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


class AuditTimelineEntry(BaseModel):
    """One mark on a claim's audit timeline: an instant (`end` is None) or a span."""

    label: str
    kind: Literal["event", "step", "review"]
    actor: str | None = None
    start: datetime
    end: datetime | None = None


class WriteHistory(BaseModel):
    """One intended ClaimsPro change: every attempt, its verify read and retries (#2)."""

    operation: str
    idempotency_key: str
    status: WriteStatus
    attempts: list[PipelineEvent]


class ClaimAudit(BaseModel):
    """The expanded audit record (#9): the required record plus how the claim was handled."""

    record: AuditRecord
    adjuster_id: str | None
    pipeline_version: str
    prompt_version: str | None
    events: list[PipelineEvent]
    timeline: list[AuditTimelineEntry]
    writes: list[WriteHistory]


SignalKind = Literal[
    "injury", "onset_gap", "causation_gap", "dispute", "low_confidence", "secondary_skill"
]


class SignalItem(BaseModel):
    """One complexity signal, with the passage it rests on. Only verified ones route."""

    kind: SignalKind
    skill: Skill | None = None
    quote: str
    source: str
    confidence: float = Field(ge=0, le=1)
    verified: bool = False


# What the complexity step's LLM may return (#4). No approve, deny or recommendation
# field anywhere. Size limits are stated to the model and enforced by trimming in
# pipeline/llm_signals.py rather than by rejecting the response: the schema and the
# quote check carry the safety, these only bound size. (The SDK moves length
# constraints into descriptions, so the model isn't held to them.)
MAX_QUOTE = 300
MAX_SIGNALS = 12


class LlmSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SignalKind
    skill: Skill | None = Field(
        default=None, description="Only for kind=secondary_skill: the second skill needed."
    )
    quote: str = Field(
        description=f"Verbatim passage from the source, copied exactly; at most {MAX_QUOTE} chars."
    )
    source: str = Field(description="File name of the document the quote is from.")
    confidence: float = Field(ge=0, le=1)


class LlmSignalsResponse(BaseModel):
    """No approve, deny or recommendation field: by construction, the model can't decide."""

    model_config = ConfigDict(extra="forbid")

    signals: list[LlmSignal] = Field(description=f"At most {MAX_SIGNALS} signals.")
    suggested_tier: Tier | None = Field(
        default=None, description="A higher handling tier, if the text shows more complexity."
    )


class Recorded(BaseModel):
    """A response saved from an earlier run: what replay and the fallback use."""

    model: str
    response: LlmSignalsResponse


class Signals(BaseModel):
    """What the complexity step (#4) reads from a claim's text.

    `secondary_skills` and `injury` are what routing reads; they come only from
    verified items. The rest is provenance for the audit record and the UI.
    """

    secondary_skills: list[Skill] = []
    injury: bool = False
    suggested_tier: Tier | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: Literal["recorded", "rules", "llm", "llm_fallback"] = "rules"
    items: list[SignalItem] = []
    llm_model: str | None = None
    latency_ms: int | None = None
    fallback: bool = False
    fallback_reason: str | None = None
    base_url_host: str | None = None

    @property
    def unverified(self) -> list[SignalItem]:
        return [i for i in self.items if not i.verified]


class Regulation(BaseModel):
    """Why a claim must reach a person. `regulated` is the law; `flagged` is discretion."""

    regulated: bool
    by_rule: bool
    flagged: bool
    reason: str | None = None

    @property
    def review_required(self) -> bool:
        return self.regulated or self.flagged


class CorrectionVerdict(BaseModel):
    """An OCR correction may change characters, never words."""

    accepted: bool
    needs_person: bool
    dropped: list[str] = []
    added: list[str] = []
    reason: str | None = None


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
    sla_state: SlaState
    regulated: bool
    routing_reason: str
    adjuster_id: str | None = None
    synthetic: bool = False


class WhatMattersPoint(BaseModel):
    text: str
    unusual: bool = False
    source: SourceRef


class KeyFact(BaseModel):
    label: str
    value: str
    unusual: bool = False
    sources: list[SourceRef] = []


class TimelineEntry(BaseModel):
    """One step of an injury timeline (Bodily Injury key facts)."""

    when: str
    event: str
    source: SourceRef


class Account(BaseModel):
    """One party's version of events, shown side by side with the others (Liability)."""

    party: str
    says: str
    source: SourceRef


class OcrWord(BaseModel):
    raw: str
    corrected: str
    negation: bool = False

    @property
    def changed(self) -> bool:
        return self.raw != self.corrected


class OcrCheck(BaseModel):
    """A raw OCR passage and its proposed correction, as written in panel content."""

    label: str
    raw: str
    corrected: str
    source: SourceRef


class OcrDiff(BaseModel):
    """Raw OCR next to its correction, word for word, with negations called out."""

    source: SourceRef
    words: list[OcrWord]
    verdict: CorrectionVerdict


class KeyFacts(BaseModel):
    template: Skill
    facts: list[KeyFact]
    collapsed: bool = True
    timeline: list[TimelineEntry] = []
    accounts: list[Account] = []


class AttentionItem(BaseModel):
    kind: Literal["missing", "conflict", "low_confidence"]
    label: str
    sources: list[SourceRef] = []
    values: list[str] = []
    suggested: str | None = None
    ocr_diff: OcrDiff | None = None


class ContentsEntry(BaseModel):
    fact: str
    location: SourceRef


class FooterTouch(BaseModel):
    actor: str
    at: datetime


class PanelFooter(BaseModel):
    touches: list[FooterTouch] = []
    pipeline_version: str
    note: str | None = None


class PanelSummary(BaseModel):
    header: PanelHeader
    what_matters: list[WhatMattersPoint] = Field(max_length=4)
    key_facts: KeyFacts
    needs_attention: list[AttentionItem] = []
    contents: list[ContentsEntry] = []
    footer: PanelFooter
    fast_lane: bool = False

    @property
    def leads_with_attention(self) -> bool:
        """A thin file: when everything to show is what's missing, show that first."""
        kinds = {item.kind for item in self.needs_attention}
        return len(self.needs_attention) > 1 and kinds == {"missing"}


class PanelContent(BaseModel):
    """The written part of a claim's panel (demo/data/panel/{claim_id}.json).

    The header and the pipeline's attention items are computed; this carries the
    rest, worded for the claim, with every point linked to its source.
    """

    what_matters: list[WhatMattersPoint] = Field(max_length=4)
    key_facts: list[KeyFact]
    timeline: list[TimelineEntry] = []
    accounts: list[Account] = []
    needs_attention: list[AttentionItem] = []
    ocr_check: OcrCheck | None = None
    contents: list[ContentsEntry] = []
    footer_note: str | None = None


class CorrectionLogEntry(BaseModel):
    """A person's confirm, correction or "this is wrong" flag from the panel."""

    claim_id: str
    section: str
    action: Literal["confirm", "correct", "request", "flag"]
    item: str | None = None
    note: str | None = None
    at: datetime


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


class HistoryLine(BaseModel):
    """One line of a multi-line plot: one group (a tier), with its own target."""

    key: str
    label: str
    target: float
    target_label: str
    points: list[HistoryPoint]


class HistoryLineSet(BaseModel):
    """Several lines of one measure on a single shared y-axis: same unit, same scale.

    Log scale when the lines sit orders of magnitude apart, so each line's
    proportional change reads at the same slope.
    """

    key: str
    label: str
    unit: str
    scale: Literal["linear", "log"] = "linear"
    source: str
    lines: list[HistoryLine] = Field(min_length=2)


class HistoryChart(BaseModel):
    """One chart box: two to four plots, each with a single y-axis, top down."""

    id: str
    title: str
    subtitle: str
    primary: HistorySeries
    secondary: HistorySeries
    tertiary: HistorySeries | None = None
    quaternary: HistoryLineSet | None = None

    @property
    def series(self) -> list[HistorySeries]:
        return [s for s in (self.primary, self.secondary, self.tertiary) if s is not None]


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
