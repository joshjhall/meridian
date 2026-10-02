import random
from datetime import datetime

import pytest

import clock
from claimspro_sim import ClaimsProSim, FaultConfig
from fixtures import extract_rows, load_claim_fixtures, load_roster
from models import Skill, Stage, Tier
from pipeline import PIPELINE_VERSION, run_pipeline
from pipeline.rules import REVIEW_LANES

FIXTURES = load_claim_fixtures()
NOW = clock.DEMO_START


@pytest.fixture(scope="module")
def fixture_run():
    return run_pipeline([f.claim for f in FIXTURES.values()], load_roster(), now=NOW).by_id()


@pytest.mark.parametrize("claim_id", sorted(FIXTURES))
def test_fixture_routes_as_the_panel_examples_say(fixture_run, claim_id):
    expected = FIXTURES[claim_id].expected
    routed = fixture_run[claim_id]
    assert routed.stage == Stage.WITH_ADJUSTER
    assert routed.claim is not None and routed.regulation is not None
    assert routed.claim.skills == expected.skills
    assert routed.claim.tier == expected.tier
    assert routed.regulation.regulated == expected.regulated
    assert routed.claim.routing_reason == expected.routing_reason
    assert routed.claim.sla_state(NOW) == expected.sla_in_demo


@pytest.mark.parametrize(
    "claim_id", ["IS-CLM-2025000375", "IS-CLM-2025004518", "IS-CLM-2025002043"]
)
def test_regulated_unflagged_claims_land_in_review(fixture_run, claim_id):
    routed = fixture_run[claim_id]
    assert routed.claim is not None
    assert routed.claim.review_lane == "regulatory_review"
    assert "required review was missing" in (routed.claim.routing_reason or "")


def test_queue_is_ordered_by_sla_left(fixture_run):
    ordered = sorted(fixture_run.values(), key=lambda r: r.queue_position or 0)
    due = [r.claim.sla_due_at for r in ordered if r.claim]
    assert due == sorted(due)


def test_senior_lane_goes_to_a_senior(fixture_run):
    roster = {a.id: a for a in load_roster()}
    for routed in fixture_run.values():
        assert routed.claim is not None and routed.adjuster_id is not None
        adjuster = roster[routed.adjuster_id]
        assert routed.claim.tier in adjuster.tiers
        if routed.claim.review_lane == "senior_review":
            assert adjuster.role in {"senior", "lead"}


def test_every_node_emits_an_event():
    result = run_pipeline([FIXTURES["IS-CLM-2025002993"].claim], load_roster(), now=NOW)
    stages = [e.stage for e in result.events]
    for stage in (Stage.VALIDATED, Stage.ENRICHED, Stage.PRIORITIZED, Stage.ASSIGNED):
        assert stage in stages
    assert stages[-1] == Stage.WITH_ADJUSTER
    assert all(e.pipeline_version == PIPELINE_VERSION for e in result.events)


def test_malformed_row_stops_for_a_person_and_is_still_audited():
    row = next(extract_rows()) | {"state": None, "claim_id": "IS-CLM-2025999999"}
    (routed,) = run_pipeline([row], load_roster(), now=NOW).routed
    assert routed.stage == Stage.EXCEPTION
    assert routed.adjuster_id is None
    assert any(i.startswith("state:") for i in routed.issues)
    assert routed.audit.rationale.startswith("Stopped for a person")


def test_no_matching_adjuster_fails_safe_to_exception():
    roster = [a for a in load_roster() if "Liability" not in a.skills]
    result = run_pipeline([FIXTURES["IS-CLM-2025004518"].claim], roster, now=NOW)
    (routed,) = result.routed
    assert routed.stage == Stage.EXCEPTION
    assert "no adjuster" in routed.issues
    assert routed.audit.output["review_lane"] == "regulatory_review"


def _sim() -> ClaimsProSim:
    claims = [f.claim for f in FIXTURES.values()]
    return ClaimsProSim(claims, sleep=lambda _s: None, now=lambda: NOW, rng=random.Random(7))


def test_custom_fields_are_written_to_claimspro():
    sim = _sim()
    result = run_pipeline([f.claim for f in FIXTURES.values()], load_roster(), now=NOW, sim=sim)
    for routed in result.routed:
        stored = sim.store.get(routed.claim_id)
        assert stored is not None and routed.claim is not None
        assert routed.write_status == "confirmed"
        assert stored.tier == routed.claim.tier
        assert stored.review_lane == routed.claim.review_lane
        assert stored.routing_reason == routed.claim.routing_reason


def test_failed_write_raises_an_alert_not_a_silent_drop():
    sim = _sim()
    sim.faults.set({"UpdateCustomFields": FaultConfig(failure_rate=1.0, mode="silent_drop")})
    result = run_pipeline([FIXTURES["IS-CLM-2025000300"].claim], load_roster(), now=NOW, sim=sim)
    (routed,) = result.routed
    assert routed.write_status == "write_failed"
    assert [a.claim_id for a in sim.alerts()] == [routed.claim_id]
    assert routed.stage == Stage.EXCEPTION
    assert routed.adjuster_id is None
    assert result.events[-1].payload["reason"] == "failed_write"
    audit = routed.audit
    assert audit.input_data_ref.startswith(f"claimspro:{routed.claim_id}@sha256:")
    assert audit.model_version == f"{PIPELINE_VERSION}+signals:rules"
    assert audit.output["issues"] and audit.output["review_lane"] == "fast_lane"
    assert audit.human_reviewed is False


@pytest.mark.parametrize("failure", ["rejected", "retries_exhausted"])
def test_a_claim_stopped_after_matching_gives_its_adjuster_back(failure):
    # Two identical adjusters. The first claim's write fails (ClaimsPro doesn't know the
    # claim, or every retry fails), so its adjuster must be free again for the second.
    template = load_roster()[0]
    roster = [
        template.model_copy(
            update={"id": i, "skills": [Skill.COLLISION], "tiers": [Tier.T1], "current_load": 0}
        )
        for i in ("ADJ-001", "ADJ-002")
    ]
    kept = FIXTURES["IS-CLM-2025000300"].claim
    failed = kept.model_copy(update={"claim_id": "IS-CLM-2025999997"})
    known = [kept] if failure == "rejected" else [kept, failed]
    sim = ClaimsProSim(known, sleep=lambda _s: None, now=lambda: NOW)
    if failure == "retries_exhausted":
        # Fail exactly the first claim's three attempts, then let writes through.
        sim.faults.set(
            {"UpdateCustomFields": FaultConfig(failure_rate=1.0, mode="fault", max_failures=3)}
        )
    routed = run_pipeline([failed, kept], roster, now=NOW, sim=sim).by_id()
    assert routed[failed.claim_id].stage == Stage.EXCEPTION
    assert routed[kept.claim_id].adjuster_id == "ADJ-001"


def test_full_extract_keeps_every_regulated_claim_with_a_person():
    rows = list(extract_rows())
    result = run_pipeline(rows, load_roster(), now=datetime(2026, 1, 1))
    assert len(result.routed) == len(rows)
    outside = [
        r.claim_id
        for r in result.routed
        if r.regulation
        and r.regulation.review_required
        and r.stage != Stage.EXCEPTION
        and (r.claim is None or r.claim.review_lane not in REVIEW_LANES)
    ]
    assert outside == []
    added = [r for r in result.routed if "required review was missing" in r.audit.rationale]
    assert len(added) == 437  # review_floor.py section 6
    for r in result.routed:
        a = r.audit
        assert a.claim_id and a.input_data_ref and a.model_version and a.output
        assert 0 <= a.confidence <= 1 and a.human_reviewed is False


def test_pipeline_events_drive_the_admin_monitor():
    from monitor import MonitorState

    claims = [f.claim for f in FIXTURES.values()]
    bad_row = next(extract_rows()) | {"state": None, "claim_id": "IS-CLM-2025999999"}
    result = run_pipeline([*claims, bad_row], load_roster(), now=NOW)
    board = MonitorState()
    for event in result.events:
        board.apply(event)
    assert {v.stage for cid, v in board.claims.items() if cid in FIXTURES} == {Stage.WITH_ADJUSTER}
    assert board.claims["IS-CLM-2025999999"].reason_label == "Missing fields"
    assert board.claims["IS-CLM-2025000375"].facts["review_lane"] == "regulatory_review"
    assert board.claims["IS-CLM-2025002993"].facts["adjuster"].endswith(")")


def test_bad_filed_date_stops_for_a_person_instead_of_crashing():
    row = next(extract_rows()) | {"filed_date": "2025-13-45", "claim_id": "IS-CLM-2025999998"}
    (routed,) = run_pipeline([row], load_roster(), now=NOW).routed
    assert routed.stage == Stage.EXCEPTION
    assert any(i.startswith(("filed_date:", "received_at:")) for i in routed.issues)


def test_unreadable_intake_source_stops_for_a_person():
    claim = FIXTURES["IS-CLM-2025002993"].claim.model_copy(
        update={
            "sources": ["sample_claims/gone/ocr_output.txt", "sample_claims/gone/edi_record.txt"]
        }
    )
    (routed,) = run_pipeline([claim], load_roster(), now=NOW).routed
    assert routed.stage == Stage.EXCEPTION
    assert routed.issues[0].startswith("intake source unreadable")


def test_duplicate_claim_id_in_a_batch_is_an_exception():
    claim = FIXTURES["IS-CLM-2025000300"].claim
    first, second = run_pipeline([claim, claim], load_roster(), now=NOW).routed
    assert first.stage == Stage.WITH_ADJUSTER
    assert second.stage == Stage.EXCEPTION
    assert "duplicate claim ID" in second.issues[0]


def test_runs_are_independent():
    claims = [f.claim for f in FIXTURES.values()]
    first = run_pipeline(claims, load_roster(), now=NOW)
    second = run_pipeline(claims, load_roster(), now=NOW)
    assert [r.adjuster_id for r in first.routed] == [r.adjuster_id for r in second.routed]
    assert len(first.events) == len(second.events)


def test_rejected_claimspro_write_goes_to_exception_and_the_batch_still_routes():
    # The sim knows only 0300, so ClaimsPro rejects the write for 4222 outright.
    sim = ClaimsProSim(
        [FIXTURES["IS-CLM-2025000300"].claim], sleep=lambda _s: None, now=lambda: NOW
    )
    claims = [FIXTURES["IS-CLM-2025000300"].claim, FIXTURES["IS-CLM-2025004222"].claim]
    routed = run_pipeline(claims, load_roster(), now=NOW, sim=sim).by_id()
    assert routed["IS-CLM-2025000300"].write_status == "confirmed"
    rejected = routed["IS-CLM-2025004222"]
    assert rejected.stage == Stage.EXCEPTION
    assert rejected.issues[0].startswith("ClaimsPro rejected the routing write")
    assert (
        rejected.audit.output["routing_reason"]
        == FIXTURES["IS-CLM-2025004222"].expected.routing_reason
    )


def test_duplicate_is_flagged_even_when_the_first_copy_stopped():
    claim = FIXTURES["IS-CLM-2025000300"].claim
    broken = claim.model_copy(update={"sources": ["../outside/ocr_output.txt", "x/edi_record.txt"]})
    first, second = run_pipeline([broken, claim], load_roster(), now=NOW).routed
    assert first.stage == Stage.EXCEPTION
    assert second.stage == Stage.EXCEPTION
    assert "duplicate claim ID" in second.issues[0]
