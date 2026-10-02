"""The expanded per-claim audit record (#9): what the admin drawer and its JSON API show.

It joins three sources on the claim ID: the pipeline's `AuditRecord` and events
(#3), the simulator's write log with every attempt and retry (#2), and review
intervals. Nothing records reviews yet, so the demo scripts them in `REVIEWS`.

While the replay (#5) is served, everything comes from its current pass: the run
the operator just watched, its writes and retries. Nothing is shown ahead of the
demo clock, so steps and reviews appear as the replay reaches them.
"""

import threading
import weakref
from datetime import datetime, timedelta
from typing import Any

import clock
import replay
from claimspro_sim import ClaimsProSim
from claimspro_sim.api import Sim
from fixtures import load_roster
from models import (
    AuditTimelineEntry,
    ClaimAudit,
    PipelineEvent,
    ReviewInterval,
    Stage,
    WriteHistory,
)
from pipeline import PipelineResult, run_pipeline

ASSIGNEE = "assignee"  # stands for whoever the pipeline routed the claim to


def audit_sim(sim: Sim) -> ClaimsProSim:
    """The simulator the audit record reads: the served replay's current pass (#5).

    Read per request: a replay restart replaces it. With no replay served, the shared
    simulator (`get_sim`, injected as `sim`).
    """
    try:
        return replay.current_sim()
    except RuntimeError:
        return sim


# Scripted handling for the demo, as offsets from assignment: (actor, start, end).
# One person can review in several non-contiguous intervals.
REVIEWS: dict[str, list[tuple[str, timedelta, timedelta]]] = {
    # The assigned senior reads the file, stops for the medical summary, picks it
    # back up, and a T3 lead signs off before the SLA runs out.
    "IS-CLM-2025004222": [
        (ASSIGNEE, timedelta(minutes=30), timedelta(hours=1, minutes=10)),
        (ASSIGNEE, timedelta(hours=2), timedelta(hours=2, minutes=40)),
        ("ADJ-114", timedelta(hours=3, minutes=15), timedelta(hours=3, minutes=35)),
    ],
}
CLOSED_AFTER: dict[str, timedelta] = {
    "IS-CLM-2025004222": timedelta(hours=3, minutes=45),
}

_runs: weakref.WeakKeyDictionary[ClaimsProSim, dict[str, PipelineResult]] = (
    weakref.WeakKeyDictionary()
)
_runs_lock = threading.Lock()


def routed(sim: ClaimsProSim, claim_id: str) -> PipelineResult:
    """The pipeline's run for this claim on this simulator.

    A replay pass kept its own run as it played, so that is read, never repeated.
    Otherwise the claim is run once per simulator: reopening never re-writes ClaimsPro.
    Raises KeyError for a claim ClaimsPro doesn't hold (or the replay hasn't reached).
    """
    kept: dict[str, PipelineResult] | None = getattr(sim, "runs", None)
    if kept is not None:
        return kept[claim_id]
    with _runs_lock:
        runs = _runs.setdefault(sim, {})
        if claim_id not in runs:
            claim = sim.store.get(claim_id)
            if claim is None:
                raise KeyError(claim_id)
            # Routed on receipt, so the timeline reads received → steps → assigned.
            runs[claim_id] = run_pipeline([claim], load_roster(), now=claim.received_at, sim=sim)
        return runs[claim_id]


def _name(adjuster_id: str | None) -> str:
    names = {a.id: a.name for a in load_roster()}
    if adjuster_id is None:
        return "unassigned"
    return f"{names[adjuster_id]} ({adjuster_id})" if adjuster_id in names else adjuster_id


def review_intervals(
    claim_id: str, assigned_at: datetime, adjuster_id: str | None, now: datetime
) -> list[ReviewInterval]:
    """Scripted reviews as of `now`: not started yet are left out, one under way is open."""
    out = []
    for actor, start, end in REVIEWS.get(claim_id, []):
        if assigned_at + start > now:
            continue
        out.append(
            ReviewInterval(
                actor=_name(adjuster_id if actor == ASSIGNEE else actor),
                start=assigned_at + start,
                end=assigned_at + end if assigned_at + end <= now else None,
            )
        )
    return out


def _step_label(event: PipelineEvent) -> str:
    step = event.payload.get("step")
    stage = str(event.stage).replace("_", " ").capitalize()
    return f"{stage}: {step.replace('_', ' ')}" if step else stage


def write_history(sim: ClaimsProSim, claim_id: str, now: datetime) -> list[WriteHistory]:
    """Every reliable write on the claim up to `now`, read live, so later retries show on reopen."""
    by_key: dict[str, list[PipelineEvent]] = {}
    for event in sim.events(claim_id):
        if event.timestamp > now:
            continue
        if "write_status" in event.payload and event.payload.get("idempotency_key"):
            by_key.setdefault(event.payload["idempotency_key"], []).append(event)
    return [
        WriteHistory(
            operation=attempts[0].payload["operation"],
            idempotency_key=key,
            status=attempts[-1].payload["write_status"],
            attempts=attempts,
        )
        for key, attempts in by_key.items()
    ]


def claim_audit(sim: ClaimsProSim, claim_id: str, now: datetime | None = None) -> ClaimAudit:
    """The record as of `now` (default the demo clock): nothing ahead of what has played."""
    now = clock.now() if now is None else now
    result = routed(sim, claim_id)
    run = result.routed[0]
    events = [e for e in result.events if e.timestamp <= now]
    claim = sim.store.get(claim_id)
    if claim is None or not events:
        raise KeyError(claim_id)  # not received yet, as far as the board has played
    assigned = next((e.timestamp for e in events if e.stage is Stage.ASSIGNED), None)
    intervals = (
        review_intervals(claim_id, assigned, run.adjuster_id, now) if assigned is not None else []
    )
    record = run.audit.model_copy(
        update={
            "review_intervals": intervals,
            "human_reviewed": any(i.end is not None for i in intervals),
        }
    )

    timeline = [
        AuditTimelineEntry(
            label=f"Received ({claim.intake_channel})", kind="event", start=claim.received_at
        )
    ]
    for e in events:
        if e.stage is Stage.RECEIVED:
            continue  # already the first entry, with its channel
        if e.stage is Stage.ASSIGNED:
            label = f"Assigned to {e.payload.get('adjuster', 'unassigned')}"
            timeline.append(AuditTimelineEntry(label=label, kind="event", start=e.timestamp))
        else:
            timeline.append(
                AuditTimelineEntry(label=_step_label(e), kind="step", start=e.timestamp)
            )
    timeline += [
        AuditTimelineEntry(label="Review", kind="review", actor=i.actor, start=i.start, end=i.end)
        for i in intervals
    ]
    if (
        assigned is not None
        and claim_id in CLOSED_AFTER
        and assigned + CLOSED_AFTER[claim_id] <= now
    ):
        closed = assigned + CLOSED_AFTER[claim_id]
        timeline.append(AuditTimelineEntry(label="Closed", kind="event", start=closed))
    timeline.sort(key=lambda t: t.start)  # stable: same-instant steps keep pipeline order

    prompt = next(
        (e.payload["prompt_version"] for e in events if "prompt_version" in e.payload), None
    )
    return ClaimAudit(
        record=record,
        adjuster_id=run.adjuster_id,
        pipeline_version=events[0].pipeline_version if events else run.audit.model_version,
        prompt_version=prompt,
        events=events,
        timeline=timeline,
        # The replay logs a claim's writes on arrival; show them once its assignment has played.
        writes=write_history(sim, claim_id, now) if assigned is not None else [],
    )


def timeline_rows(timeline: list[AuditTimelineEntry]) -> dict[str, Any]:
    """Lay the timeline out as rows of bars, in percent of received → last mark."""
    t0 = min(t.start for t in timeline)
    t1 = max(t.end or t.start for t in timeline)
    span = (t1 - t0).total_seconds() or 1.0

    def pct(at: datetime) -> float:
        return round(100 * (at - t0).total_seconds() / span, 2)

    rows: dict[str, list[dict[str, Any]]] = {"Claim": []}
    for t in timeline:
        mark = {
            "label": t.label,
            "left": pct(t.start),
            "kind": t.kind,
            "start": t.start,
            "end": t.end,
        }
        if t.end is not None:
            mark["width"] = max(pct(t.end) - mark["left"], 0.5)
        rows.setdefault(t.actor or "Claim", []).append(mark)
    return {"start": t0, "end": t1, "rows": rows}
