"""Expanded audit record (#9): the five fields, rationale, timeline, versions, write history."""

import random
import re

import audit_view
import monitor
import pytest
from fastapi.testclient import TestClient

import clock
from app import app, render_card, transfer_runner
from claimspro_sim import ClaimsProSim, FaultConfig
from claimspro_sim.api import get_sim

CLAIM_4222 = "IS-CLM-2025004222"
LEAD = "ADJ-114"  # a T3 lead with Bodily Injury: an eligible target for 4222
BOARD = {"X-Meridian-Board": "1"}


@pytest.fixture(autouse=True)
def _clock():
    clock.reset()
    yield
    clock.reset()


@pytest.fixture
def sim() -> ClaimsProSim:
    return ClaimsProSim(sleep=lambda _s: None, now=clock.now, rng=random.Random(9))


@pytest.fixture
def client(sim: ClaimsProSim):
    app.dependency_overrides[get_sim] = lambda: sim
    app.dependency_overrides[transfer_runner] = lambda: lambda job: job()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_audit_sim_is_the_shared_simulator(client: TestClient, sim: ClaimsProSim):
    # The one seam #40 swaps for the replay runner's simulator.
    assert audit_view.audit_sim(sim) is sim
    client.get(f"/api/claims/{CLAIM_4222}/audit")
    assert sim.events(CLAIM_4222), "the pipeline's write should land in the shared sim"


def test_4222_shows_the_five_fields_and_rationale(client: TestClient, sim: ClaimsProSim):
    audit = audit_view.claim_audit(sim, CLAIM_4222)
    r = audit.record
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


def test_4222_timeline_has_non_contiguous_reviews_by_one_person(
    client: TestClient, sim: ClaimsProSim
):
    audit = audit_view.claim_audit(sim, CLAIM_4222)
    reviews = [t for t in audit.timeline if t.kind == "review"]
    by_actor: dict[str, list] = {}
    for t in reviews:
        by_actor.setdefault(t.actor or "", []).append(t)
    senior = by_actor[f"Victor Quintero ({audit.adjuster_id})"]
    assert len(senior) == 2
    first, second = sorted(senior, key=lambda t: t.start)
    assert first.end is not None and first.end < second.start
    assert len(by_actor) == 2, "the lead signs off in a separate interval"
    labels = [t.label for t in audit.timeline]
    assert labels[0] == "Received (Phone)"
    assert sum(label.startswith("Received") for label in labels) == 1
    assert audit.timeline[-1].label == "Closed"

    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    row = re.search(r'data-actor="Victor Quintero \(ADJ-\d{3}\)">(.*?)</div>', html, flags=re.S)
    assert row is not None
    assert row.group(1).count("timeline__bar") == 2


def test_versions_match_the_pipeline_events(client: TestClient, sim: ClaimsProSim):
    audit = audit_view.claim_audit(sim, CLAIM_4222)
    assert {e.pipeline_version for e in audit.events} == {audit.pipeline_version}
    prompts = {e.payload["prompt_version"] for e in audit.events if "prompt_version" in e.payload}
    assert prompts == {audit.prompt_version}
    # The monitor's feed and the pipeline share one version.
    assert audit.pipeline_version == monitor.PIPELINE_VERSION

    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    assert f'<code data-version="pipeline">{audit.pipeline_version}</code>' in html
    assert f'<code data-version="prompt">{audit.prompt_version}</code>' in html


def test_write_history_shows_retries_when_the_fault_switch_was_on(
    client: TestClient, sim: ClaimsProSim
):
    sim.faults.set({"UpdateCustomFields": FaultConfig(failure_rate=1.0, max_failures=1)})
    [write] = audit_view.claim_audit(sim, CLAIM_4222).writes
    assert write.operation == "UpdateCustomFields"
    assert [a.payload["write_status"] for a in write.attempts] == [
        "pending",
        "retrying",
        "confirmed",
    ]
    html = client.get(f"/admin/claims/{CLAIM_4222}/audit").text
    assert 'data-write-status="retrying"' in html
    assert "2 attempts" in html


def test_a_later_failed_move_shows_on_reopen(client: TestClient, sim: ClaimsProSim):
    client.get(f"/admin/claims/{CLAIM_4222}/audit")
    client.post("/admin/queues/faults", params={"on": "true", "view": "admin"}, headers=BOARD)
    client.post(
        f"/admin/queues/claims/{CLAIM_4222}/transfer",
        params={"to": LEAD, "view": "admin"},
        headers=BOARD,
    )
    writes = audit_view.claim_audit(sim, CLAIM_4222).writes
    move = next(w for w in writes if w.operation == "TransferWorkItem")
    assert move.status == "failed"
    assert [a.payload["write_status"] for a in move.attempts] == [
        "pending",
        "retrying",
        "retrying",
        "failed",
    ]


def test_reopening_does_not_rerun_the_pipeline(client: TestClient, sim: ClaimsProSim):
    client.get(f"/admin/claims/{CLAIM_4222}/audit")
    before = len(sim.events(CLAIM_4222))
    client.get(f"/admin/claims/{CLAIM_4222}/audit")
    client.get(f"/api/claims/{CLAIM_4222}/audit")
    assert len(sim.events(CLAIM_4222)) == before


def test_api_returns_the_same_record_as_json(client: TestClient):
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


def test_claim_without_scripted_reviews_is_not_reviewed(client: TestClient, sim: ClaimsProSim):
    audit = audit_view.claim_audit(sim, "IS-CLM-2025000300")
    assert audit.record.human_reviewed is False
    assert not any(t.kind == "review" for t in audit.timeline)
    assert "Not reviewed yet." in client.get("/admin/claims/IS-CLM-2025000300/audit").text


@pytest.mark.parametrize("path", ["/api/claims/{}/audit", "/admin/claims/{}/audit"])
def test_unknown_claim_is_404(client: TestClient, path: str):
    assert client.get(path.format("IS-CLM-0000000000")).status_code == 404


def test_demo_cards_open_the_audit_and_background_cards_the_trace():
    claims = monitor.replay().claims.values()
    pinned = next(v for v in claims if v.pinned)
    background = next(v for v in claims if not v.pinned)
    assert f"/admin/claims/{pinned.claim_id}/audit" in render_card(pinned)
    assert 'hx-target="#audit-body"' in render_card(pinned)
    assert "/trace?upto=" in render_card(background)


def test_monitor_page_has_the_audit_drawer(client: TestClient):
    html = client.get("/admin").text
    assert 'id="audit-body"' in html
