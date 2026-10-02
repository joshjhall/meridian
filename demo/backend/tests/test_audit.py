"""Expanded audit record (#9): five fields, rationale, timeline, versions, write history.

The drawer reads the served replay's current pass (#5): the run the operator watched.
With no replay served it falls back to the shared simulator and runs the claim once.
"""

import random
import re
from datetime import datetime, timedelta

import audit_view
import pytest
from fastapi.testclient import TestClient

import clock
from app import app, render_card
from claimspro_sim import ClaimsProSim, FaultConfig
from claimspro_sim.api import get_sim
from models import AuditTimelineEntry, Stage
from pipeline.audit import PIPELINE_VERSION
from pipeline.signals import PROMPT_VERSION
from replay import runner, schedule

CLAIM_4222 = "IS-CLM-2025004222"
CLAIM_300 = "IS-CLM-2025000300"

client = TestClient(app)  # no lifespan: the replay only moves when a test steps it


@pytest.fixture
def replay():
    r = app.state.replay
    r.restart()
    yield r
    r.set(speed=runner.DEFAULT_SPEED, paused=False)
    r.restart(schedule.SEED)


def _play_until_assigned(replay, claim_id: str) -> None:
    def done() -> bool:
        view = replay.board.claims.get(claim_id)
        return view is not None and view.stage is Stage.WITH_ADJUSTER

    while not done():
        assert replay.step() is not None


def _let_time_pass(hours: float) -> datetime:
    """Move the demo clock on, as the replay does between events."""
    return clock.advance(timedelta(hours=hours))


# --- Live: the served replay ---


def test_audit_sim_is_the_replays_current_pass(replay):
    sim = ClaimsProSim()
    assert audit_view.audit_sim(sim) is replay.sim
    replay.restart()
    assert audit_view.audit_sim(sim) is replay.sim  # per request: a restart replaces it


def test_drawer_shows_the_run_the_replay_played(replay):
    _play_until_assigned(replay, CLAIM_4222)
    writes_before = len(replay.sim.events(CLAIM_4222))
    audit = audit_view.claim_audit(replay.sim, CLAIM_4222)
    assert audit.events == replay.board.claims[CLAIM_4222].trace
    # Reading never runs the pipeline again: no new writes on the replay's ClaimsPro.
    client.get(f"/admin/claims/{CLAIM_4222}/audit")
    client.get(f"/api/claims/{CLAIM_4222}/audit")
    assert len(replay.sim.events(CLAIM_4222)) == writes_before
    [write] = audit.writes
    assert write.operation == "UpdateCustomFields"
    assert write.status == "confirmed"


def test_nothing_shows_ahead_of_the_board(replay):
    while CLAIM_4222 not in replay.board.claims:
        assert replay.step() is not None
    audit = audit_view.claim_audit(replay.sim, CLAIM_4222)
    assert audit.events == replay.board.claims[CLAIM_4222].trace
    assert audit.writes == []  # its write shows once the assignment has played
    assert audit.record.review_intervals == []


def test_claim_not_reached_yet_is_404(replay):
    assert client.get(f"/admin/claims/{CLAIM_4222}/audit").status_code == 404


def test_4222_shows_the_five_fields_and_rationale(replay):
    _play_until_assigned(replay, CLAIM_4222)
    _let_time_pass(4)
    r = audit_view.claim_audit(replay.sim, CLAIM_4222).record
    assert r.input_data_ref.startswith(f"claimspro:{CLAIM_4222}@sha256:")
    assert r.output["review_lane"] == "senior_review"
    assert r.confidence == 0.9
    assert r.human_reviewed is True

    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    for label in ("Input data", "Model version", "Output", "Confidence", "Human reviewed"):
        assert f"<dt>{label}</dt>" in html
    assert r.input_data_ref in html
    assert r.model_version in html
    assert "90%" in html
    assert "BI over $10K in NY → T3 senior first" in html
    assert "Chat history (P2)" in html


def test_4222_timeline_has_non_contiguous_reviews_by_one_person(replay):
    _play_until_assigned(replay, CLAIM_4222)
    _let_time_pass(4)
    audit = audit_view.claim_audit(replay.sim, CLAIM_4222)
    by_actor: dict[str, list[AuditTimelineEntry]] = {}
    for t in audit.timeline:
        if t.kind == "review":
            by_actor.setdefault(t.actor or "", []).append(t)
    senior = by_actor[audit_view._name(audit.adjuster_id)]
    assert len(senior) == 2
    first, second = senior
    assert first.end is not None and first.end < second.start
    assert len(by_actor) == 2, "a lead signs off in a separate interval"
    labels = [t.label for t in audit.timeline]
    assert sum(label.startswith("Received") for label in labels) == 1
    assert labels[-1] == "Closed"
    assert [t.start for t in audit.timeline] == sorted(t.start for t in audit.timeline)

    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    row = re.search(r'data-actor="[^"]*\(ADJ-\d{3}\)">(.*?)</div>', html, flags=re.S)
    assert row is not None
    assert row.group(1).count("timeline__bar") == 2


def test_reviews_appear_as_the_clock_reaches_them(replay):
    _play_until_assigned(replay, CLAIM_4222)
    assert audit_view.claim_audit(replay.sim, CLAIM_4222).record.review_intervals == []
    _let_time_pass(0.75)  # inside the senior's first interval
    record = audit_view.claim_audit(replay.sim, CLAIM_4222).record
    [under_way] = record.review_intervals
    assert under_way.end is None
    assert record.human_reviewed is False


def test_between_reviews_shows_only_what_has_happened(replay):
    _play_until_assigned(replay, CLAIM_4222)
    _let_time_pass(2.9)  # the senior is done; the lead hasn't started; not closed
    audit = audit_view.claim_audit(replay.sim, CLAIM_4222)
    intervals = audit.record.review_intervals
    assert len(intervals) == 2 and all(i.end is not None for i in intervals)
    assert audit.record.human_reviewed is True
    assert "Closed" not in [t.label for t in audit.timeline]


def test_write_history_hides_attempts_after_now(replay):
    _play_until_assigned(replay, CLAIM_4222)
    [write] = audit_view.write_history(replay.sim, CLAIM_4222, clock.now())
    first = write.attempts[0].timestamp
    before = audit_view.write_history(replay.sim, CLAIM_4222, first - timedelta(seconds=1))
    assert before == []


def test_versions_match_the_pipeline_events(replay):
    _play_until_assigned(replay, CLAIM_4222)
    audit = audit_view.claim_audit(replay.sim, CLAIM_4222)
    assert {e.pipeline_version for e in audit.events} == {audit.pipeline_version}
    assert audit.pipeline_version == PIPELINE_VERSION
    prompts = {e.payload["prompt_version"] for e in audit.events if "prompt_version" in e.payload}
    assert prompts == {audit.prompt_version} == {PROMPT_VERSION}

    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    assert f'<code data-version="pipeline">{audit.pipeline_version}</code>' in html
    assert f'<code data-version="prompt">{audit.prompt_version}</code>' in html


def test_seeded_outage_shows_its_retries_and_failure(replay):
    def failed():
        return next(
            (v for v in replay.board.claims.values() if v.facts.get("reason") == "failed_write"),
            None,
        )

    while (view := failed()) is None:
        assert replay.step() is not None
    [write] = audit_view.claim_audit(replay.sim, view.claim_id).writes
    assert write.status == "failed"
    assert [a.payload["write_status"] for a in write.attempts] == [
        "pending",
        "retrying",
        "retrying",
        "failed",
    ]
    html = client.get(f"/admin/claims/{view.claim_id}/audit").text
    assert 'data-write-status="retrying"' in html


def test_api_returns_the_same_record_as_json(replay):
    _play_until_assigned(replay, CLAIM_4222)
    _let_time_pass(4)
    body = client.get(f"/api/claims/{CLAIM_4222}/audit").json()
    assert set(body["record"]) >= {
        "input_data_ref",
        "model_version",
        "output",
        "confidence",
        "human_reviewed",
        "rationale",
    }
    assert len(body["record"]["review_intervals"]) == 3


def test_claim_without_scripted_reviews_is_not_reviewed(replay):
    _play_until_assigned(replay, CLAIM_300)
    _let_time_pass(4)
    audit = audit_view.claim_audit(replay.sim, CLAIM_300)
    assert audit.record.human_reviewed is False
    assert not any(t.kind == "review" for t in audit.timeline)
    assert "Not reviewed yet." in client.get(f"/admin/claims/{CLAIM_300}/audit").text


@pytest.mark.parametrize("path", ["/api/claims/{}/audit", "/admin/claims/{}/audit"])
def test_unknown_claim_is_404(replay, path: str):
    assert client.get(path.format("IS-CLM-0000000000")).status_code == 404


def test_demo_cards_open_the_audit_and_background_cards_the_trace(replay):
    _play_until_assigned(replay, CLAIM_300)
    pinned = replay.board.claims[CLAIM_300]
    background = next(v for v in replay.board.claims.values() if not v.pinned)
    assert f"/admin/claims/{CLAIM_300}/audit" in render_card(pinned)
    assert 'hx-target="#audit-body"' in render_card(pinned)
    assert "/trace?upto=" in render_card(background)


def test_monitor_page_has_the_audit_drawer():
    assert 'id="audit-body"' in client.get("/admin").text


# --- Fallback: no replay served ---


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setattr(runner, "_served", None)
    clock.reset()
    s = ClaimsProSim(sleep=lambda _s: None, now=clock.now, rng=random.Random(9))
    app.dependency_overrides[get_sim] = lambda: s
    yield s
    app.dependency_overrides.clear()
    clock.reset()


def test_without_a_replay_the_shared_sim_is_read(sim: ClaimsProSim):
    assert audit_view.audit_sim(sim) is sim
    assert client.get(f"/api/claims/{CLAIM_4222}/audit").status_code == 200
    assert sim.events(CLAIM_4222), "the claim is run once against the shared simulator"


def test_fallback_unknown_claim_raises(sim: ClaimsProSim):
    with pytest.raises(KeyError):
        audit_view.claim_audit(sim, "IS-CLM-0000000000")


def test_fallback_runs_once_and_shows_faulted_retries(sim: ClaimsProSim):
    sim.faults.set({"UpdateCustomFields": FaultConfig(failure_rate=1.0, max_failures=1)})
    [write] = audit_view.claim_audit(sim, CLAIM_4222).writes
    assert [a.payload["write_status"] for a in write.attempts] == [
        "pending",
        "retrying",
        "confirmed",
    ]
    before = len(sim.events(CLAIM_4222))
    client.get(f"/admin/claims/{CLAIM_4222}/audit")
    assert len(sim.events(CLAIM_4222)) == before


# --- Layout ---


def test_timeline_rows_lay_out_marks_and_bars():
    t0 = datetime(2025, 10, 15, 9, 0)
    rows = audit_view.timeline_rows(
        [
            AuditTimelineEntry(label="Received", kind="event", start=t0),
            AuditTimelineEntry(
                label="Review",
                kind="review",
                actor="A",
                start=t0 + timedelta(hours=1),
                end=t0 + timedelta(hours=1, seconds=1),
            ),
            AuditTimelineEntry(label="Closed", kind="event", start=t0 + timedelta(hours=2)),
        ]
    )["rows"]
    assert [m["left"] for m in rows["Claim"]] == [0.0, 100.0]
    [bar] = rows["A"]
    assert bar["left"] == 50.0 and bar["width"] == 0.5  # a very short review stays visible
    one_instant = audit_view.timeline_rows([AuditTimelineEntry(label="x", kind="event", start=t0)])
    assert one_instant["rows"]["Claim"][0]["left"] == 0.0
