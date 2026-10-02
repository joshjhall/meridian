import pytest
from pipeline import rules

from fixtures import load_claim_fixtures
from models import AttentionItem, Signals, Tier

FIXTURES = load_claim_fixtures()


def _claim(**update):
    return FIXTURES["IS-CLM-2025000300"].claim.model_copy(update=update)


@pytest.mark.parametrize(
    ("label", "flag", "state", "amount", "regulated", "by_rule", "reason"),
    [
        ("No", "No", "FL", 2_000, False, False, None),
        ("No", "No", "FL", 12_000, True, True, "regulated (FL, over $10K)"),
        ("Yes", "No", "TX", 3_000, True, False, "regulated — rule unknown"),
        ("No", "Yes", "TX", 3_000, False, False, "flagged for review"),
        ("No", "No", "MD", 10_001, True, True, "regulated (MD, over $10K)"),
        ("No", "No", "CA", 10_000, False, False, None),
    ],
)
def test_regulatory_check_routes_on_both_flags_and_the_rule(
    label, flag, state, amount, regulated, by_rule, reason
):
    claim = _claim(
        requires_human_by_regulation=label,
        flagged_for_human_review=flag,
        state=state,
        claim_amount_usd=amount,
    )
    reg = rules.regulatory_check(claim)
    assert (reg.regulated, reg.by_rule, reg.reason) == (regulated, by_rule, reason)
    assert reg.review_required == (regulated or flag == "Yes")


def test_twelve_rule_states():
    assert len(rules.RULE_STATES) == 12


def test_review_required_never_reaches_the_fast_lane():
    for label, flag in (("Yes", "No"), ("No", "Yes")):
        reg = rules.regulatory_check(
            _claim(requires_human_by_regulation=label, flagged_for_human_review=flag)
        )
        assert rules.review_lane(Tier.T1, reg, []) in rules.REVIEW_LANES


def test_attention_items_keep_a_claim_out_of_the_fast_lane():
    reg = rules.regulatory_check(_claim())
    item = AttentionItem(kind="missing", label="photos")
    assert rules.review_lane(Tier.T1, reg, []) == "fast_lane"
    assert rules.review_lane(Tier.T1, reg, [item]) == "standard_review"


def test_rule_unknown_reason_names_the_state():
    claim = _claim(requires_human_by_regulation="Yes", state="TX", claim_amount_usd=4_000)
    reg = rules.regulatory_check(claim)
    reason = rules.routing_reason(claim, Tier.T1, "regulatory_review", reg, [])
    assert reason == "Regulated (TX, rule unknown): required review was missing; added"


def test_injury_signal_lifts_a_simple_claim_off_t1():
    _, tier = rules.classify(_claim(), Signals(injury=True))
    assert tier == Tier.T2


def test_priority_puts_breached_first_then_review_required():
    from datetime import timedelta

    base = _claim()
    now = base.sla_due_at - timedelta(hours=10)
    late = base.model_copy(update={"received_at": base.received_at - timedelta(hours=20)})
    reg_none = rules.regulatory_check(base)
    reg_flag = rules.regulatory_check(_claim(flagged_for_human_review="Yes"))
    keys = {
        "late": rules.priority_key(late, Tier.T1, reg_none, now),
        "flagged": rules.priority_key(base, Tier.T1, reg_flag, now),
        "plain": rules.priority_key(base, Tier.T1, reg_none, now),
    }
    assert sorted(keys, key=keys.__getitem__) == ["late", "flagged", "plain"]
