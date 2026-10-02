import inspect
import logging
import random
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import clock
from app import app
from claimspro_sim import ALERT_RECIPIENTS, ClaimsProSim, FaultConfig, reliable_write, store
from claimspro_sim.api import get_sim
from claimspro_sim.soap import ClaimsProSoapClient, SoapClientError
from claimspro_sim.store import IdempotencyKeyConflict, seed_claims
from fixtures import load_claim_fixtures
from models import Skill, Tier

CLAIM = "IS-CLM-2025000300"
NOW = datetime(2025, 6, 19, 9, 0)


@pytest.fixture
def sim() -> ClaimsProSim:
    return ClaimsProSim(sleep=lambda _s: None, now=lambda: NOW, rng=random.Random(7))


@pytest.fixture
def client(sim: ClaimsProSim):
    app.dependency_overrides[get_sim] = lambda: sim
    yield TestClient(app)
    app.dependency_overrides.clear()


def statuses(sim: ClaimsProSim, claim_id: str = CLAIM) -> list[str]:
    return [e.payload["write_status"] for e in sim.events(claim_id)]


CUSTOM = {
    "skills": ["Collision"],
    "tier": "T2",
    "routing_reason": "test",
    "review_lane": "fast_lane",
}


# --- Reads ---


def test_reads_return_all_six_fixture_claims_with_custom_fields(client):
    for cid in load_claim_fixtures():
        body = client.get(f"/api/claimspro/claims/{cid}").json()
        assert body["claim_id"] == cid
        for field in ("skills", "tier", "routing_reason", "review_lane", "brief_status"):
            assert field in body


def test_read_unknown_claim_is_404(client):
    assert client.get("/api/claimspro/claims/IS-CLM-0000000000").status_code == 404


def test_store_also_holds_the_extracts_open_work(sim):
    claims = sim.store.list_claims()
    assert len(claims) > 6
    extract_only = [c for c in claims if c.claim_id not in load_claim_fixtures()]
    assert extract_only and all(c.disposition == "Pending Review" for c in extract_only)


def test_list_filters_by_assignee(client, sim):
    assignee = sim.store.get(CLAIM).adjuster_id
    body = client.get("/api/claimspro/claims", params={"assignee": assignee}).json()
    assert CLAIM in {c["claim_id"] for c in body}
    assert {c["adjuster_id"] for c in body} == {assignee}


# --- Writes persist ---


def test_custom_field_write_persists_and_is_visible_on_next_read(client, sim):
    result = reliable_write(sim, "UpdateCustomFields", CLAIM, {"fields": CUSTOM})
    assert result.status == "confirmed"
    assert result.attempts == 1
    body = client.get(f"/api/claimspro/claims/{CLAIM}").json()
    assert body["skills"] == ["Collision"]
    assert body["tier"] == "T2"
    assert body["review_lane"] == "fast_lane"
    assert body["write_status"] == "confirmed"
    assert statuses(sim) == ["pending", "confirmed"]


def test_transfer_write_persists_and_is_visible_on_next_read(client, sim):
    result = reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    assert result.status == "confirmed"
    assert client.get(f"/api/claimspro/claims/{CLAIM}").json()["adjuster_id"] == "ADJ-151"
    moved = client.get("/api/claimspro/claims", params={"assignee": "ADJ-151"}).json()
    assert CLAIM in {c["claim_id"] for c in moved}


def test_writes_never_mutate_the_cached_fixtures(sim):
    reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    reliable_write(sim, "UpdateCustomFields", CLAIM, {"fields": CUSTOM})
    original = load_claim_fixtures()[CLAIM].claim
    assert original.adjuster_id != "ADJ-151"
    assert original.tier is None
    assert original.write_status is None


def test_store_reads_are_snapshots(sim):
    sim.store.get(CLAIM).tier = Tier.T3  # type: ignore[union-attr]
    assert sim.store.get(CLAIM).tier is None  # type: ignore[union-attr]


# --- Fault switch, verify and retry ---


def test_fault_switch_round_trips_over_http(client):
    config = {"TransferWorkItem": {"failure_rate": 0.5, "mode": "silent_drop", "latency_ms": 200}}
    assert client.post("/api/sim/faults", json=config).status_code == 200
    got = client.get("/api/sim/faults").json()
    assert got["TransferWorkItem"]["mode"] == "silent_drop"
    assert client.delete("/api/sim/faults").json() == {}


def test_fault_switch_rejects_unknown_operations(client):
    resp = client.post("/api/sim/faults", json={"DenyClaim": {"failure_rate": 1}})
    assert resp.status_code == 422


def test_silent_drop_is_caught_by_verify_read_and_retried(sim):
    sim.faults.set(
        {"TransferWorkItem": FaultConfig(failure_rate=1, mode="silent_drop", max_failures=1)}
    )
    result = reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    assert result.status == "confirmed"
    assert result.attempts == 2
    assert statuses(sim) == ["pending", "retrying", "confirmed"]
    retry = sim.events(CLAIM)[1]
    assert "verify read" in retry.payload["reason"]
    assert sim.store.get(CLAIM).adjuster_id == "ADJ-151"  # type: ignore[union-attr]


def test_backoff_grows_between_retries(sim):
    slept: list[float] = []
    sim.sleep = slept.append
    sim.faults.set({"AddNote": FaultConfig(failure_rate=1, mode="fault")})
    reliable_write(
        sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"},
        max_attempts=3, verify_delay_s=0.2, base_backoff_s=0.5,
    )  # fmt: skip
    # verify wait after every attempt; doubling backoff between attempts
    assert slept == [0.2, 0.5, 0.2, 1.0, 0.2]


def test_after_n_failed_attempts_item_is_write_failed_and_alert_emitted(client, sim):
    sim.faults.set({"TransferWorkItem": FaultConfig(failure_rate=1, mode="silent_drop")})
    result = reliable_write(
        sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"}, max_attempts=4
    )
    assert result.status == "write_failed"
    assert result.attempts == 4
    assert statuses(sim) == ["pending", "retrying", "retrying", "retrying", "failed"]
    assert client.get(f"/api/claimspro/claims/{CLAIM}").json()["write_status"] == "write_failed"
    alerts = client.get("/api/sim/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["claim_id"] == CLAIM
    assert alerts[0]["recipients"] == ALERT_RECIPIENTS
    assert alerts[0]["idempotency_key"] == result.idempotency_key


def test_write_events_are_pipeline_events_visible_over_http(client, sim):
    reliable_write(sim, "UpdateCustomFields", CLAIM, {"fields": CUSTOM})
    events = client.get("/api/sim/events", params={"claim_id": CLAIM}).json()
    assert [e["payload"]["write_status"] for e in events] == ["pending", "confirmed"]
    assert all(e["payload"]["operation"] == "UpdateCustomFields" for e in events)


# --- Idempotency ---


def test_lost_response_is_confirmed_by_verify_read_not_reapplied(sim):
    sim.faults.set({"AddNote": FaultConfig(failure_rate=1, mode="lost_response")})
    result = reliable_write(sim, "AddNote", CLAIM, {"text": "Routed", "author": "pipeline"})
    assert result.status == "confirmed"
    assert result.attempts == 1  # the write landed; only its response was lost
    assert len(sim.store.notes(CLAIM)) == 1
    assert sim.alerts() == []


def test_resending_after_lost_response_never_applies_the_change_twice(sim):
    sim.faults.set({"AddNote": FaultConfig(failure_rate=1, mode="lost_response")})
    first = sim.soap.AddNote(CLAIM, "Routed", "pipeline", idempotency_key="k1")
    assert not first.ok  # applied, but the caller can't tell
    sim.faults.reset()
    second = sim.soap.AddNote(CLAIM, "Routed", "pipeline", idempotency_key="k1")
    assert second.ok
    assert len(sim.store.notes(CLAIM)) == 1


def test_retry_after_fault_then_silent_drop_applies_once(sim):
    sim.faults.set({"AddNote": FaultConfig(failure_rate=1, mode="fault", max_failures=1)})
    result = reliable_write(sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"})
    assert result.attempts == 2
    assert len(sim.store.notes(CLAIM)) == 1


def test_key_reused_for_a_different_change_is_rejected(sim):
    sim.soap.AddNote(CLAIM, "x", "pipeline", idempotency_key="k1")
    with pytest.raises(ValueError, match="already used"):
        sim.soap.TransferWorkItem(CLAIM, "ADJ-151", idempotency_key="k1")
    assert sim.store.get(CLAIM).adjuster_id != "ADJ-151"  # type: ignore[union-attr]


def test_replaying_the_same_key_never_applies_twice(sim):
    payload = {"text": "hello", "author": "pipeline"}
    first = reliable_write(sim, "AddNote", CLAIM, payload)
    reliable_write(sim, "AddNote", CLAIM, payload, idempotency_key=first.idempotency_key)
    assert len(sim.store.notes(CLAIM)) == 1


def test_control_distinct_intended_changes_each_apply(sim):
    payload = {"text": "hello", "author": "pipeline"}
    reliable_write(sim, "AddNote", CLAIM, payload)
    reliable_write(sim, "AddNote", CLAIM, payload)
    assert len(sim.store.notes(CLAIM)) == 2


# --- No decisioning ---


def test_no_operation_approves_or_denies_a_claim():
    ops = {
        name
        for name, _ in inspect.getmembers(ClaimsProSoapClient, inspect.isfunction)
        if name[0].isupper()
    }
    assert ops == {"UpdateCustomFields", "AddNote", "TransferWorkItem"}
    every_member = " ".join(dir(ClaimsProSoapClient)).lower()
    for word in ("approve", "deny", "denial", "disposition", "adjudicat", "decide"):
        assert word not in every_member


@pytest.mark.parametrize(
    "fields", [{"disposition": "Denied"}, {"denial_reason": "x"}, {"claim_amount_usd": 1.0}]
)
def test_custom_field_write_cannot_set_decision_or_claim_data(sim, fields):
    with pytest.raises(SoapClientError):
        sim.soap.UpdateCustomFields(CLAIM, fields, "k1")
    assert sim.store.get(CLAIM).disposition == load_claim_fixtures()[CLAIM].claim.disposition  # type: ignore[union-attr]


def test_invalid_requests_are_rejected_not_retried(sim):
    with pytest.raises(SoapClientError):
        reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-999"})
    with pytest.raises(SoapClientError):
        reliable_write(sim, "UpdateCustomFields", CLAIM, {"fields": {"tier": "T9"}})
    with pytest.raises(SoapClientError):
        reliable_write(sim, "AddNote", "IS-CLM-0000000000", {"text": "x", "author": "y"})


def test_custom_field_values_are_parsed_to_model_types(sim):
    reliable_write(sim, "UpdateCustomFields", CLAIM, {"fields": CUSTOM})
    claim = sim.store.get(CLAIM)
    assert claim is not None
    assert claim.skills == [Skill.COLLISION]
    assert claim.tier is Tier.T2


def test_rejected_request_leaves_no_trace(sim):
    with pytest.raises(SoapClientError):
        reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-999"})
    assert sim.store.get(CLAIM).write_status is None  # type: ignore[union-attr]
    assert sim.events() == []


def test_notes_are_readable_over_http(client, sim):
    reliable_write(sim, "AddNote", CLAIM, {"text": "Routed to Collision T2", "author": "pipeline"})
    notes = client.get(f"/api/claimspro/claims/{CLAIM}/notes").json()
    assert [n["text"] for n in notes] == ["Routed to Collision T2"]
    assert client.get("/api/claimspro/claims/IS-CLM-0000000000/notes").status_code == 404


def test_fault_switch_fractional_rate_is_seeded_and_mixed():
    def outcomes(seed: int) -> list[bool]:
        sim = ClaimsProSim(sleep=lambda _s: None, now=lambda: NOW, rng=random.Random(seed))
        sim.faults.set({"AddNote": FaultConfig(failure_rate=0.5)})
        return [sim.faults.roll("AddNote")[0] is not None for _ in range(40)]

    assert outcomes(1) == outcomes(1)
    assert 0 < sum(outcomes(1)) < 40


def test_fault_latency_is_applied_whether_or_not_the_call_fails(sim):
    slept: list[float] = []
    sim.soap._sleep = slept.append
    sim.faults.set({"AddNote": FaultConfig(latency_ms=250, failure_rate=1, max_failures=1)})
    sim.soap.AddNote(CLAIM, "a", "p", idempotency_key="k1")
    sim.soap.AddNote(CLAIM, "b", "p", idempotency_key="k2")
    assert slept == [0.25, 0.25]


def test_setting_faults_resets_the_failure_counter(sim):
    config = FaultConfig(failure_rate=1, max_failures=1)
    sim.faults.set({"AddNote": config})
    assert sim.faults.roll("AddNote")[0] == "fault"
    assert sim.faults.roll("AddNote")[0] is None
    sim.faults.set({"AddNote": config})
    assert sim.faults.roll("AddNote")[0] == "fault"


@pytest.mark.parametrize(
    "config", [{"failure_rate": 1.5}, {"latency_ms": -1}, {"latency_ms": 60_000}, {"mode": "x"}]
)
def test_invalid_fault_config_is_rejected(client, config):
    assert client.post("/api/sim/faults", json={"AddNote": config}).status_code == 422


def test_persistent_lost_response_on_transfer_still_confirms(sim):
    sim.faults.set({"TransferWorkItem": FaultConfig(failure_rate=1, mode="lost_response")})
    result = reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    assert result.status == "confirmed"
    assert statuses(sim) == ["pending", "confirmed"]


def test_reused_key_is_rejected_before_the_claim_goes_pending(sim):
    first = reliable_write(sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"})
    events_before = len(sim.events())
    with pytest.raises(IdempotencyKeyConflict):
        reliable_write(
            sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"},
            idempotency_key=first.idempotency_key,
        )  # fmt: skip
    assert sim.store.get(CLAIM).write_status == "confirmed"  # type: ignore[union-attr]
    assert len(sim.events()) == events_before


@pytest.mark.parametrize(
    ("op", "payload"),
    [
        ("UpdateCustomFields", {}),
        ("UpdateCustomFields", {"fields": ["tier"]}),
        ("TransferWorkItem", {"adjuster": "ADJ-151"}),
        ("TransferWorkItem", {"to_adjuster_id": 151}),
        ("AddNote", {"text": "x"}),
        ("AddNote", {"text": "x", "author": "y", "extra": "z"}),
    ],
)
def test_malformed_payload_is_rejected_before_any_state_change(sim, op, payload):
    with pytest.raises(SoapClientError):
        reliable_write(sim, op, CLAIM, payload)
    assert sim.store.get(CLAIM).write_status is None  # type: ignore[union-attr]
    assert sim.events() == []


def test_unexpected_error_mid_write_marks_failed_and_alerts(sim, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("ClaimsPro connection reset")

    monkeypatch.setattr(sim.soap, "call", boom)
    with pytest.raises(RuntimeError):
        reliable_write(sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"})
    assert sim.store.get(CLAIM).write_status == "write_failed"  # type: ignore[union-attr]
    assert statuses(sim) == ["pending", "failed"]
    assert [a.recipients for a in sim.alerts()] == [ALERT_RECIPIENTS]


def test_fault_reset_and_event_filter_over_http(client, sim):
    client.post("/api/sim/faults", json={"AddNote": {"failure_rate": 1}})
    assert client.delete("/api/sim/faults").json() == {}
    assert client.get("/api/sim/faults").json() == {}
    reliable_write(sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"})
    other = "IS-CLM-2025004222"
    assert client.get("/api/sim/events", params={"claim_id": other}).json() == []
    assert len(client.get("/api/sim/events", params={"claim_id": CLAIM}).json()) == 2


def test_key_reused_with_a_different_payload_is_rejected(sim):
    first = reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    with pytest.raises(IdempotencyKeyConflict):
        reliable_write(
            sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-152"},
            idempotency_key=first.idempotency_key,
        )  # fmt: skip
    assert sim.store.get(CLAIM).adjuster_id == "ADJ-151"  # type: ignore[union-attr]


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_max_attempts_below_one_is_rejected_before_any_state_change(sim, max_attempts):
    with pytest.raises(ValueError, match="max_attempts"):
        reliable_write(
            sim, "AddNote", CLAIM, {"text": "x", "author": "p"}, max_attempts=max_attempts
        )
    assert sim.store.get(CLAIM).write_status is None  # type: ignore[union-attr]
    assert sim.events() == []


def test_replay_after_a_later_write_still_confirms(sim):
    first = reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"})
    reliable_write(sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-152"})
    replay = reliable_write(
        sim, "TransferWorkItem", CLAIM, {"to_adjuster_id": "ADJ-151"},
        idempotency_key=first.idempotency_key,
    )  # fmt: skip
    assert replay.status == "confirmed"
    assert sim.store.get(CLAIM).adjuster_id == "ADJ-152"  # type: ignore[union-attr]
    assert sim.alerts() == []


def test_events_are_stamped_with_the_demo_clock_by_default():
    sim = ClaimsProSim(sleep=lambda _s: None)
    reliable_write(sim, "AddNote", CLAIM, {"text": "x", "author": "pipeline"})
    assert {e.timestamp for e in sim.events()} == {clock.now()}


def test_seed_claims_takes_open_extract_work_and_fixtures_win():
    seeded = {c.claim_id: c for c in seed_claims()}
    fixtures = load_claim_fixtures()
    for claim_id, fixture in fixtures.items():
        assert seeded[claim_id] == fixture.claim
    extract_only = [c for cid, c in seeded.items() if cid not in fixtures]
    assert extract_only
    assert {c.disposition for c in extract_only} == {"Pending Review"}


def test_malformed_extract_row_is_skipped_and_logged_not_fatal(monkeypatch, caplog):
    good = next(r for r in store.extract_rows() if r["disposition"] == "Pending Review")
    bad = {**good, "claim_id": "IS-CLM-BAD", "claim_amount_usd": "not-a-number"}
    monkeypatch.setattr(store, "extract_rows", lambda: iter([bad, good]))

    with caplog.at_level(logging.WARNING, logger=store.__name__):
        ids = {c.claim_id for c in seed_claims()}

    assert good["claim_id"] in ids and "IS-CLM-BAD" not in ids
    [warning] = [r.getMessage() for r in caplog.records if "IS-CLM-BAD" in r.getMessage()]
    assert "claim_amount_usd:" in warning
