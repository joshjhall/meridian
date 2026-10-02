"""Admin pipeline monitor (#6): fixture feed, state, page, stream, trace."""

import json
from itertools import pairwise

import monitor
import pytest
from fastapi.testclient import TestClient

from app import app, render_card
from fixtures import load_claim_fixtures
from models import ExceptionReason, Stage

client = TestClient(app)

CLAIM_2993 = "IS-CLM-2025002993"


def test_script_is_time_ordered_and_deterministic():
    script = monitor.fixture_script()
    assert [s.at for s in script] == sorted(s.at for s in script)
    assert monitor.fixture_script.__wrapped__() == script


def test_every_fixture_claim_reaches_its_expected_end_state():
    state = monitor.replay()
    for claim_id, fx in load_claim_fixtures().items():
        view = state.claims[claim_id]
        assert view.pinned
        assert view.story == monitor.STORIES[claim_id]
        if claim_id == CLAIM_2993:
            # Fails safe at validation, before enrichment learns its skills or tier.
            assert view.stage is Stage.EXCEPTION
            continue
        assert view.stage is Stage.WITH_ADJUSTER, claim_id
        assert view.facts["tier"] == fx.expected.tier
        assert view.facts["skills"] == [str(s) for s in fx.expected.skills]
        assert view.facts["regulated"] == fx.expected.regulated


def test_2993_waits_in_exceptions_with_its_named_conflicts():
    view = monitor.replay().claims[CLAIM_2993]
    assert view.facts["reason"] == ExceptionReason.OCR_CONFLICT
    fields = [c["field"] for c in view.facts["conflicts"]]
    assert fields == ["Policy number", "Bumper line", "Date of loss", "Claimant contact"]
    policy = view.facts["conflicts"][0]
    assert (policy["ocr"], policy["edi"]) == ("CA-CA-88l23-l8", "CA-CA-88123-18")


def test_exceptions_lane_shows_more_than_one_reason():
    state = monitor.replay()
    reasons = {v.facts["reason"] for v in state.claims.values() if v.stage is Stage.EXCEPTION}
    assert len(reasons) >= 2


def test_counters_track_open_exceptions_and_routed_claims():
    state = monitor.MonitorState()
    seen_exceptions = []
    for s in monitor.fixture_script():
        state.apply(s.event)
        seen_exceptions.append(state.open_exceptions)
    # A claim recovers from the exceptions lane, so the count goes down at least once.
    assert any(b < a for a, b in pairwise(seen_exceptions))
    assert state.open_exceptions == sum(v.stage is Stage.EXCEPTION for v in state.claims.values())
    # 2993 is regulated but stops before prioritization, so it isn't routed yet.
    assert CLAIM_2993 not in state.routed_to_review
    assert "IS-CLM-2025000375" in state.routed_to_review
    assert "IS-CLM-2025000300" not in state.routed_to_review


def test_routed_claim_is_counted_once():
    state = monitor.MonitorState()
    for s in monitor.fixture_script():
        if s.event.claim_id == "IS-CLM-2025004222":
            state.apply(s.event)
    assert state.counters()["routed"] == 1


def test_admin_page_has_lanes_counters_and_stream():
    html = client.get("/admin").text
    for stage in Stage:
        assert f'data-lane="{stage}"' in html
    assert "Regulated claims routed to review" in html
    assert "Open exceptions" in html
    assert 'data-events-url="/admin/events"' in html
    assert "/static/admin.js" in html


def test_role_switch_leaves_admin_controls_out_for_managers():
    assert 'id="admin-controls"' in client.get("/admin?view=admin").text
    manager = client.get("/admin?view=manager").text
    assert 'id="admin-controls"' not in manager
    assert "Pause feed" not in manager
    assert client.get("/admin?view=root").status_code == 422


def _frames(text: str) -> list[tuple[str, dict]]:
    frames = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append((lines["event"], json.loads(lines["data"])))
    return frames


def test_event_stream_sends_rendered_cards_and_counters():
    limit = len(monitor.fixture_script())
    response = client.get(f"/admin/events?speed=100&limit={limit}")
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response.text)
    # Each pass opens with a reset, so a reconnecting browser clears its board.
    assert frames[0] == ("reset", {"counters": {"routed": 0, "exceptions": 0}})
    claims = [d for name, d in frames if name == "claim"]
    assert len(claims) == limit == len(frames) - 1
    last = {d["claim_id"]: d for d in claims}
    card = last[CLAIM_2993]
    assert card["stage"] == "exception"
    assert 'id="card-IS-CLM-2025002993"' in card["html"]
    assert "claim--pinned" in card["html"]
    assert "Policy number" in card["html"]
    final = claims[-1]["counters"]
    assert final == monitor.replay().counters()


def test_trace_lists_the_exception_step_with_conflicts():
    html = client.get(f"/admin/claims/{CLAIM_2993}/trace").text
    assert "OCR conflicts with EDI" in html
    assert "CA-CA-88l23-l8" in html
    assert "routing-v0.4.0" in html


def test_every_pass_of_the_stream_opens_with_a_reset(monkeypatch):
    monkeypatch.setattr(monitor, "HOLD_S", 0.0)
    limit = len(monitor.fixture_script()) + 1  # one claim frame into the second pass
    frames = _frames(client.get(f"/admin/events?speed=100&limit={limit}").text)
    names = [name for name, _ in frames]
    assert names == ["reset", *["claim"] * (limit - 1), "reset", "claim"]


def test_trace_stops_where_the_card_is():
    html = client.get(f"/admin/claims/{CLAIM_2993}/trace?upto=1").text
    assert "Received" in html
    assert "OCR conflicts with EDI" not in html


def test_trace_upto_past_the_end_is_the_whole_trace():
    whole = client.get(f"/admin/claims/{CLAIM_2993}/trace").text
    assert client.get(f"/admin/claims/{CLAIM_2993}/trace?upto=999").text == whole


def test_card_links_its_trace_at_the_steps_it_has_seen():
    view = monitor.replay().claims[CLAIM_2993]
    assert f"/trace?upto={len(view.trace)}" in render_card(view)


@pytest.mark.parametrize("query", ["speed=0", "speed=101", "limit=0"])
def test_event_stream_rejects_out_of_range_params(query):
    assert client.get(f"/admin/events?{query}").status_code == 422


@pytest.mark.parametrize("upto", [0, -1])
def test_trace_rejects_out_of_range_upto(upto):
    assert client.get(f"/admin/claims/{CLAIM_2993}/trace?upto={upto}").status_code == 422


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


def test_trace_unknown_claim_is_404():
    assert client.get("/admin/claims/IS-CLM-0000000000/trace").status_code == 404
