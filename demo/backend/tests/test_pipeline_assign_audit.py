import random

import pytest

from claimspro_sim import ClaimsProSim
from fixtures import load_claim_fixtures, load_roster
from models import Adjuster, AdjusterRole, Signals, Skill, Tier
from pipeline.assign import Loads, match, route_problems
from pipeline.audit import PIPELINE_VERSION, build_audit, input_data_ref, write_custom_fields
from pipeline.signals import complexity_signals

CLAIM = load_claim_fixtures()["IS-CLM-2025000300"].claim


def _adj(
    id_: str, skills: list[Skill], tiers: list[Tier], role: AdjusterRole = "adjuster", load: int = 0
) -> Adjuster:
    return Adjuster(
        id=id_,
        name=id_,
        skills=skills,
        tiers=tiers,
        role=role,
        current_load=load,
        extract_code=False,
    )


def test_match_takes_the_lightest_load_and_spreads_work():
    loads = Loads(
        [
            _adj("ADJ-001", [Skill.COLLISION], [Tier.T1], load=1),
            _adj("ADJ-002", [Skill.COLLISION], [Tier.T1], load=1),
        ]
    )
    picks = [match([Skill.COLLISION], Tier.T1, "fast_lane", loads)[0] for _ in range(3)]
    assert [a.id for a in picks if a] == ["ADJ-001", "ADJ-002", "ADJ-001"]


def test_match_falls_back_to_the_primary_skill():
    loads = Loads([_adj("ADJ-001", [Skill.LIABILITY], [Tier.T2])])
    adjuster, how = match([Skill.LIABILITY, Skill.COLLISION], Tier.T2, "regulatory_review", loads)
    assert adjuster is not None and how == "primary skill only"


def test_senior_lane_needs_a_senior_or_lead():
    loads = Loads([_adj("ADJ-001", [Skill.BODILY_INJURY], [Tier.T3])])
    assert match([Skill.BODILY_INJURY], Tier.T3, "senior_review", loads)[0] is None
    loads = Loads([_adj("ADJ-002", [Skill.BODILY_INJURY], [Tier.T3], role="lead")])
    assert match([Skill.BODILY_INJURY], Tier.T3, "senior_review", loads)[0] is not None


def test_route_problems_name_every_inconsistency():
    t1_only = _adj("ADJ-001", [Skill.COLLISION], [Tier.T1])
    problems = route_problems(
        skills=[], tier=Tier.T2, lane="fast_lane", review_required=True, adjuster=t1_only
    )
    assert problems == [
        "no skills",
        "review required but routed to fast_lane",
        "ADJ-001 does not work T2",
    ]
    assert route_problems(
        skills=[Skill.COLLISION], tier=None, lane=None, review_required=False, adjuster=None
    ) == ["no tier", "no lane", "no adjuster"]


def test_audit_record_has_the_five_fields_and_a_rationale():
    signals = Signals(confidence=0.7, source="recorded")
    record = build_audit(CLAIM, signals, {"tier": "T1"}, "why")
    assert record.input_data_ref == input_data_ref(CLAIM)
    assert record.model_version == f"{PIPELINE_VERSION}+signals:recorded"
    assert record.output["tier"] == "T1"
    assert record.output["signals"]["source"] == "recorded"
    assert record.confidence == 0.7
    assert record.human_reviewed is False
    assert record.rationale == "why"


def test_input_ref_ignores_routing_fields_but_tracks_inputs():
    routed = CLAIM.model_copy(update={"tier": Tier.T1, "routing_reason": "x"})
    assert input_data_ref(routed) == input_data_ref(CLAIM)
    changed = CLAIM.model_copy(update={"claim_amount_usd": 1.0})
    assert input_data_ref(changed) != input_data_ref(CLAIM)


def test_custom_field_write_is_replayed_not_repeated():
    sim = ClaimsProSim([CLAIM], sleep=lambda _s: None, rng=random.Random(7))
    routed = CLAIM.model_copy(
        update={
            "skills": [Skill.COLLISION],
            "tier": Tier.T1,
            "routing_reason": "r",
            "review_lane": "fast_lane",
        }
    )
    first = write_custom_fields(sim, routed)
    second = write_custom_fields(sim, routed)
    assert first is not None and second is not None
    assert first.status == second.status == "confirmed"
    assert first.idempotency_key == second.idempotency_key
    assert write_custom_fields(None, routed) is None


def test_roster_has_a_senior_for_every_skill():
    seniors = [a for a in load_roster() if a.role in {"senior", "lead"} and Tier.T3 in a.tiers]
    assert {s for a in seniors for s in a.skills} == set(Skill)


def test_complexity_signals_recorded_for_fixtures_and_empty_otherwise():
    fixtures = load_claim_fixtures()
    recorded = complexity_signals(fixtures["IS-CLM-2025002993"].claim)
    assert recorded.source == "recorded" and recorded.llm_model
    assert recorded.secondary_skills == [Skill.COLLISION]
    assert recorded.injury and recorded.confidence == 0.69
    assert recorded.items and all(i.verified for i in recorded.items)
    plain = complexity_signals(CLAIM.model_copy(update={"claim_id": "IS-CLM-2025999999"}))
    assert (plain.source, plain.secondary_skills, plain.confidence) == ("rules", [], 1.0)
    assert plain.llm_model is None


def test_release_undoes_take_and_refuses_an_unmatched_release():
    loads = Loads([_adj("ADJ-001", [Skill.COLLISION], [Tier.T1], load=0)])
    loads.take("ADJ-001")
    loads.release("ADJ-001")
    assert loads["ADJ-001"] == 0
    with pytest.raises(ValueError, match="release without take"):
        loads.release("ADJ-001")
