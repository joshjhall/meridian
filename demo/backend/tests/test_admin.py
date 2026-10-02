"""Admin pipeline monitor (#6): board state, page, cards and trace over the live replay."""

import monitor
import pytest
from fastapi.testclient import TestClient

from app import app, render_card
from clock import DEMO_START
from models import EXCEPTION_LABELS, ExceptionReason, PipelineEvent, Stage

client = TestClient(app)  # no lifespan: the replay only moves when a test steps it

CLAIM_300 = "IS-CLM-2025000300"


@pytest.fixture
def replay():
    r = app.state.replay
    r.restart()
    yield r
    r.restart()


def _play_until(replay, done):
    while not done(replay.board):
        assert replay.step() is not None


def _event(claim_id: str, stage: Stage, **payload) -> PipelineEvent:
    return PipelineEvent(
        claim_id=claim_id,
        stage=stage,
        timestamp=DEMO_START,
        payload=payload,
        pipeline_version="test",
    )


def test_board_counts_regulated_claims_routed_to_review_once():
    state = monitor.MonitorState()
    for stage in (Stage.PRIORITIZED, Stage.ASSIGNED, Stage.WITH_ADJUSTER):
        state.apply(
            _event("IS-CLM-2025000375", stage, regulated=True, review_lane="regulatory_review")
        )
    state.apply(
        _event("IS-CLM-2025000001", Stage.PRIORITIZED, regulated=True, review_lane="fast_lane")
    )
    state.apply(
        _event("IS-CLM-2025000002", Stage.PRIORITIZED, regulated=False, review_lane="senior_review")
    )
    assert state.counters() == {"routed": 1, "exceptions": 0}


def test_exception_reason_clears_when_the_claim_moves_on():
    state = monitor.MonitorState()
    state.apply(_event(CLAIM_300, Stage.EXCEPTION, reason="failed_write", issues=["x"]))
    assert state.claims[CLAIM_300].reason_label == "ClaimsPro write failed"
    assert state.open_exceptions == 1
    view = state.apply(_event(CLAIM_300, Stage.WITH_ADJUSTER, adjuster_id="ADJ-101"))
    assert view.reason_label is None and "issues" not in view.facts
    assert state.open_exceptions == 0


def test_every_exception_reason_has_a_label():
    assert set(EXCEPTION_LABELS) == set(ExceptionReason)


def test_admin_page_has_lanes_counters_and_stream():
    html = client.get("/admin").text
    for stage in Stage:
        assert f'data-lane="{stage}"' in html
    assert "Regulated claims routed to review" in html
    assert "Open exceptions" in html
    assert 'data-events-url="/api/events"' in html
    assert "/static/admin.js" in html


def test_role_switch_leaves_admin_controls_out_for_managers():
    assert 'id="admin-controls"' in client.get("/admin?view=admin").text
    manager = client.get("/admin?view=manager").text
    assert 'id="admin-controls"' not in manager
    assert "Pause feed" not in manager
    assert client.get("/admin?view=root").status_code == 422


def test_trace_lists_every_step_a_live_card_has_seen(replay):
    _play_until(
        replay, lambda b: CLAIM_300 in b.claims and b.claims[CLAIM_300].stage is Stage.WITH_ADJUSTER
    )
    view = replay.board.claims[CLAIM_300]
    html = client.get(f"/admin/claims/{CLAIM_300}/trace").text
    assert html.count('class="trace__step') == len(view.trace)
    assert "pipeline-0.1" in html
    assert f"/trace?upto={len(view.trace)}" in render_card(view)


def test_trace_stops_where_the_card_is(replay):
    _play_until(
        replay, lambda b: CLAIM_300 in b.claims and b.claims[CLAIM_300].stage is Stage.WITH_ADJUSTER
    )
    whole = client.get(f"/admin/claims/{CLAIM_300}/trace").text
    first = client.get(f"/admin/claims/{CLAIM_300}/trace?upto=1").text
    assert first.count('class="trace__step') == 1
    assert "Received" in first
    assert client.get(f"/admin/claims/{CLAIM_300}/trace?upto=999").text == whole
    # Truncating a trace for the dialog never truncates the live card.
    assert client.get(f"/admin/claims/{CLAIM_300}/trace").text == whole


def test_exception_card_and_trace_name_the_reason_and_issues(replay):
    _play_until(replay, lambda b: b.open_exceptions > 0)
    view = next(v for v in replay.board.claims.values() if v.stage is Stage.EXCEPTION)
    label = EXCEPTION_LABELS[ExceptionReason(view.facts["reason"])]
    assert label in render_card(view)
    html = client.get(f"/admin/claims/{view.claim_id}/trace").text
    assert label in html
    for issue in view.facts["issues"]:
        assert issue in html


@pytest.mark.parametrize("upto", [0, -1])
def test_trace_rejects_out_of_range_upto(upto):
    assert client.get(f"/admin/claims/{CLAIM_300}/trace?upto={upto}").status_code == 422


def test_card_escapes_feed_text():
    view = monitor.ClaimView(
        claim_id="IS-CLM-2025000001",
        stage=Stage.ASSIGNED,
        pinned=False,
        story=None,
        facts={"adjuster": "<script>alert(1)</script>"},
    )
    html = render_card(view)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_trace_unknown_claim_is_404(replay):
    assert client.get("/admin/claims/IS-CLM-0000000000/trace").status_code == 404
