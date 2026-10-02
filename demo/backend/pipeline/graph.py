"""The pre-processing and routing pipeline as LangGraph graphs.

    pipeline:  enrich (per claim) → prioritize (whole queue) → route (per claim, in order)
    enrich:    validate → ocr_check → classify → regulatory
    route:     assign → validate_route → audit_write

Any node that finds a problem sends the claim to `exception`, which interrupts the
graph so a person resolves it: nothing is dropped and nothing is guessed. Every node
emits a PipelineEvent. The pipeline orders, explains and records; it never approves
or denies a claim.
"""

# LangGraph fills the state node by node; the edges guarantee a key is set before a
# node reads it, which pyright cannot see through total=False TypedDicts.
# pyright: reportTypedDictNotRequiredAccess=false

import operator
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from claimspro_sim import ClaimsProSim
from claimspro_sim.soap import SoapClientError
from models import (
    Adjuster,
    AttentionItem,
    AuditRecord,
    Claim,
    ExceptionReason,
    PipelineEvent,
    Regulation,
    ReviewLane,
    Signals,
    Skill,
    Stage,
    Tier,
)
from pipeline import intake, rules
from pipeline.assign import Loads, match, route_problems
from pipeline.audit import PIPELINE_VERSION, build_audit, model_version, write_custom_fields
from pipeline.signals import PROMPT_VERSION, complexity_signals


class ClaimState(TypedDict, total=False):
    raw: Claim | dict[str, Any]
    claim: Claim
    now: datetime
    signals: Signals
    regulation: Regulation
    attention: list[AttentionItem]
    skills: list[Skill]
    tier: Tier
    lane: ReviewLane
    adjuster: Adjuster
    matched_on: str
    issues: list[str]
    audit: AuditRecord
    events: Annotated[list[PipelineEvent], operator.add]


class Routed(BaseModel):
    """One claim's outcome. `exception` claims wait for a person; nothing else is skipped."""

    claim_id: str
    claim: Claim | None
    stage: Stage
    regulation: Regulation | None = None
    attention: list[AttentionItem] = []
    adjuster_id: str | None = None
    queue_position: int | None = None
    issues: list[str] = []
    audit: AuditRecord
    write_status: str | None = None


class PipelineState(TypedDict, total=False):
    inputs: list[Claim | dict[str, Any]]
    now: datetime
    enriched: list[ClaimState]
    queue: list[ClaimState]
    results: list[Routed]
    events: Annotated[list[PipelineEvent], operator.add]


def _event(claim_id: str, stage: Stage, now: datetime, **payload: Any) -> PipelineEvent:
    return PipelineEvent(
        claim_id=claim_id,
        stage=stage,
        timestamp=now,
        payload=payload,
        pipeline_version=PIPELINE_VERSION,
    )


def _raw_id(raw: Claim | dict[str, Any]) -> str:
    return raw.claim_id if isinstance(raw, Claim) else str(raw.get("claim_id") or "unknown")


def _fail_safe_to(target: str) -> Callable[[ClaimState], str]:
    return lambda state: "exception" if state.get("issues") else target


def _exception(state: ClaimState) -> ClaimState:
    claim_id = state["claim"].claim_id if "claim" in state else _raw_id(state["raw"])
    interrupt({"claim_id": claim_id, "issues": state["issues"]})
    return {}


# --- enrich: one claim, intake to regulatory status ---


def _validate(state: ClaimState) -> ClaimState:
    claim, issues = intake.validate(state["raw"])
    claim_id = claim.claim_id if claim else _raw_id(state["raw"])
    if claim is None:
        return {
            "issues": issues,
            "events": [
                _event(
                    claim_id,
                    Stage.EXCEPTION,
                    state["now"],
                    reason=ExceptionReason.MISSING_FIELDS.value,
                    issues=issues,
                )
            ],
        }
    attention = intake.intake_gaps(claim)
    received = _event(
        claim_id,
        Stage.RECEIVED,
        state["now"],
        state=claim.state,
        channel=claim.intake_channel,
        amount=claim.claim_amount_usd,
    )
    validated = _event(
        claim_id,
        Stage.VALIDATED,
        state["now"],
        fields_complete=not attention,
        missing=[a.label for a in attention],
    )
    return {"claim": claim, "attention": attention, "issues": [], "events": [received, validated]}


def _ocr_check(state: ClaimState) -> ClaimState:
    try:
        found = intake.ocr_cross_check(state["claim"])
    except intake.UnreadableSource as e:
        issues = [str(e)]
        event = _event(
            state["claim"].claim_id,
            Stage.EXCEPTION,
            state["now"],
            reason=ExceptionReason.MISSING_FIELDS.value,
            issues=issues,
        )
        return {"issues": issues, "events": [event]}
    event = _event(
        state["claim"].claim_id,
        Stage.ENRICHED,
        state["now"],
        step="ocr_check",
        proposals=[a.label for a in found],
        applied=[],
    )
    return {"attention": state["attention"] + found, "events": [event]}


def _classify(state: ClaimState) -> ClaimState:
    signals = complexity_signals(state["claim"])
    skills, tier = rules.classify(state["claim"], signals)
    event = _event(
        state["claim"].claim_id,
        Stage.ENRICHED,
        state["now"],
        step="classify",
        skills=[k.value for k in skills],
        tier=tier,
        signals=signals.source,
        prompt_version=PROMPT_VERSION,
        llm_model=signals.llm_model,
        fallback=signals.fallback,
    )
    return {"signals": signals, "skills": skills, "tier": tier, "events": [event]}


def _regulatory(state: ClaimState) -> ClaimState:
    regulation = rules.regulatory_check(state["claim"])
    lane = rules.review_lane(state["tier"], regulation, state["attention"])
    event = _event(
        state["claim"].claim_id,
        Stage.ENRICHED,
        state["now"],
        step="regulatory",
        regulated=regulation.regulated,
        review_required=regulation.review_required,
        regulation_reason=regulation.reason,
        lane=lane,
    )
    return {"regulation": regulation, "lane": lane, "events": [event]}


def build_enrich_graph():
    g = StateGraph(ClaimState)
    g.add_node("validate", _validate)
    g.add_node("ocr_check", _ocr_check)
    g.add_node("classify", _classify)
    g.add_node("regulatory", _regulatory)
    g.add_node("exception", _exception)
    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", _fail_safe_to("ocr_check"), ["ocr_check", "exception"])
    g.add_conditional_edges("ocr_check", _fail_safe_to("classify"), ["classify", "exception"])
    g.add_edge("classify", "regulatory")
    g.add_edge("regulatory", END)
    g.add_edge("exception", END)
    return g.compile(checkpointer=InMemorySaver())


# --- route: one claim, in priority order, to an adjuster and an audit record ---


def _decision(state: ClaimState) -> tuple[dict[str, Any], str]:
    claim, regulation = state["claim"], state["regulation"]
    reason = rules.routing_reason(
        claim, state["tier"], state["lane"], regulation, state["attention"]
    )
    adjuster = state.get("adjuster")
    output = {
        "skills": [k.value for k in state["skills"]],
        "tier": state["tier"].value,
        "review_lane": state["lane"],
        "regulated": regulation.regulated,
        "review_required": regulation.review_required,
        "routing_reason": reason,
        "adjuster_id": adjuster.id if adjuster else None,
        "needs_attention": [a.label for a in state["attention"]],
    }
    return output, reason


def build_route_graph(loads: Loads, sim: ClaimsProSim | None):
    def assign(state: ClaimState) -> ClaimState:
        adjuster, how = match(state["skills"], state["tier"], state["lane"], loads)
        event = _event(
            state["claim"].claim_id,
            Stage.ASSIGNED,
            state["now"],
            adjuster=f"{adjuster.name} ({adjuster.id})" if adjuster else "unassigned",
            adjuster_id=adjuster.id if adjuster else None,
            matched_on=how,
            lane=state["lane"],
        )
        update: ClaimState = {"matched_on": how, "events": [event]}
        if adjuster:
            update["adjuster"] = adjuster
        return update

    def validate_route(state: ClaimState) -> ClaimState:
        issues = route_problems(
            skills=state["skills"],
            tier=state.get("tier"),
            lane=state.get("lane"),
            review_required=state["regulation"].review_required,
            adjuster=state.get("adjuster"),
        )
        if not issues:
            return {"issues": []}
        event = _event(
            state["claim"].claim_id,
            Stage.EXCEPTION,
            state["now"],
            reason=ExceptionReason.UNKNOWN_RULE.value,
            issues=issues,
        )
        return {"issues": issues, "events": [event]}

    def audit_write(state: ClaimState) -> ClaimState:
        output, reason = _decision(state)
        claim = state["claim"].model_copy(
            update={
                "skills": state["skills"],
                "tier": state["tier"],
                "routing_reason": reason,
                "review_lane": state["lane"],
                "brief_status": "pending",
            }
        )
        rationale = f"{reason}. Assigned to {state['adjuster'].id} ({state['matched_on']})."
        audit = build_audit(claim, state["signals"], output, rationale)
        try:
            written = write_custom_fields(sim, claim)
        except SoapClientError as e:
            issues = [f"ClaimsPro rejected the routing write: {e}"]
            event = _event(
                claim.claim_id,
                Stage.EXCEPTION,
                state["now"],
                reason=ExceptionReason.FAILED_WRITE.value,
                issues=issues,
            )
            return {"claim": claim, "issues": issues, "events": [event]}
        if written is not None:
            claim = claim.model_copy(update={"write_status": written.status})
        if claim.write_status == "write_failed":
            # Retries exhausted and an alert raised; ClaimsPro doesn't show this routing,
            # so the claim waits for a person rather than reading as with the adjuster.
            issues = ["ClaimsPro write failed after retries; routing not saved"]
            event = _event(
                claim.claim_id,
                Stage.EXCEPTION,
                state["now"],
                reason=ExceptionReason.FAILED_WRITE.value,
                issues=issues,
            )
            return {"claim": claim, "issues": issues, "events": [event]}
        event = _event(
            claim.claim_id,
            Stage.WITH_ADJUSTER,
            state["now"],
            adjuster_id=state["adjuster"].id,
            write_status=claim.write_status,
        )
        return {"claim": claim, "audit": audit, "events": [event]}

    g = StateGraph(ClaimState)
    g.add_node("assign", assign)
    g.add_node("validate_route", validate_route)
    g.add_node("audit_write", audit_write)
    g.add_node("exception", _exception)
    g.add_edge(START, "assign")
    g.add_edge("assign", "validate_route")
    g.add_conditional_edges(
        "validate_route", _fail_safe_to("audit_write"), ["audit_write", "exception"]
    )
    g.add_conditional_edges("audit_write", _fail_safe_to(END), [END, "exception"])
    g.add_edge("exception", END)
    return g.compile(checkpointer=InMemorySaver())


# --- the whole run ---


def _exception_audit(state: ClaimState) -> AuditRecord:
    """Claims stopped for a person are recorded too, with what stopped them."""
    claim_id = state["claim"].claim_id if "claim" in state else _raw_id(state["raw"])
    signals = state.get("signals", Signals(source="rules"))
    output: dict[str, Any] = {"stage": Stage.EXCEPTION.value, "issues": state["issues"]}
    if "regulation" in state:
        output |= _decision(state)[0]
    rationale = "Stopped for a person: " + "; ".join(state["issues"])
    if "claim" in state:
        return build_audit(state["claim"], signals, output, rationale)
    return AuditRecord(
        claim_id=claim_id,
        input_data_ref=f"extract-row:{claim_id}",
        model_version=model_version(signals),
        output=output,
        confidence=0.0,
        human_reviewed=False,
        rationale=rationale,
    )


def build_pipeline(roster: Iterable[Adjuster], sim: ClaimsProSim | None = None):
    """One pipeline run. Build a fresh one per run: adjuster loads and checkpoints are per run."""
    enrich_graph = build_enrich_graph()
    loads = Loads(roster)
    route_graph = build_route_graph(loads, sim)

    def run(graph, state: ClaimState, n: int) -> ClaimState:
        # n is the claim's input position, so even a repeated claim ID gets its own thread.
        thread = {"configurable": {"thread_id": f"{n}:{_raw_id(state['raw'])}"}}
        return graph.invoke(state, thread)  # type: ignore[return-value]

    def enrich(state: PipelineState) -> PipelineState:
        enriched = [
            run(enrich_graph, {"raw": raw, "now": state["now"]}, n)
            for n, raw in enumerate(state["inputs"])
        ]
        seen: set[str] = set()
        for c in enriched:
            claim_id = _raw_id(c["raw"])
            if claim_id in seen and not c.get("issues"):
                issue = f"duplicate claim ID {claim_id} in this batch"
                c["issues"] = [issue]
                c["events"] = [
                    *c.get("events", []),
                    _event(
                        claim_id,
                        Stage.EXCEPTION,
                        state["now"],
                        reason=ExceptionReason.MISSING_FIELDS.value,
                        issues=[issue],
                    ),
                ]
            seen.add(claim_id)
        events = [e for c in enriched for e in c.get("events", [])]
        return {"enriched": enriched, "events": events}

    def prioritize(state: PipelineState) -> PipelineState:
        ready = [c for c in state["enriched"] if not c.get("issues")]
        queue = sorted(
            ready,
            key=lambda c: rules.priority_key(c["claim"], c["tier"], c["regulation"], state["now"]),
        )
        events = [
            _event(
                c["claim"].claim_id,
                Stage.PRIORITIZED,
                state["now"],
                position=i,
                tier=c["tier"].value,
                regulated=c["regulation"].regulated,
                review_lane=c["lane"],
                sla=c["claim"].sla_state(state["now"]),
                sla_due_at=c["claim"].sla_due_at.isoformat(),
                routing_reason=_decision(c)[1],
            )
            for i, c in enumerate(queue, start=1)
        ]
        return {"queue": queue, "events": events}

    def route(state: PipelineState) -> PipelineState:
        results: list[Routed] = []
        events: list[PipelineEvent] = []
        for position, c in enumerate(state["queue"], start=1):
            done = run(route_graph, {**c, "events": []}, position)
            if done.get("issues") and "adjuster" in done:
                loads.release(done["adjuster"].id)
            events += done.get("events", [])
            results.append(_routed(done, position))
        for c in state["enriched"]:
            if c.get("issues"):
                results.append(_routed(c, None))
        return {"results": results, "events": events}

    g = StateGraph(PipelineState)
    g.add_node("enrich", enrich)
    g.add_node("prioritize", prioritize)
    g.add_node("route", route)
    g.add_edge(START, "enrich")
    g.add_edge("enrich", "prioritize")
    g.add_edge("prioritize", "route")
    g.add_edge("route", END)
    return g.compile()


def _routed(state: ClaimState, position: int | None) -> Routed:
    claim = state.get("claim")
    stopped = bool(state.get("issues"))
    adjuster = state.get("adjuster")
    return Routed(
        claim_id=claim.claim_id if claim else _raw_id(state["raw"]),
        claim=claim,
        stage=Stage.EXCEPTION if stopped else Stage.WITH_ADJUSTER,
        regulation=state.get("regulation"),
        attention=state.get("attention", []),
        adjuster_id=adjuster.id if adjuster and not stopped else None,
        queue_position=position,
        issues=state.get("issues", []),
        audit=_exception_audit(state) if stopped else state["audit"],
        write_status=claim.write_status if claim else None,
    )
