"""Routing rules: pure functions from a claim (plus what intake found) to a routing decision.

The pipeline orders, explains and records. Nothing here approves or denies a claim.
Numbers and states come from analysis/review_floor.py (sections 2, 6 and 9).
"""

from datetime import datetime

from models import (
    TIER_LABELS,
    AttentionItem,
    Claim,
    Complexity,
    Regulation,
    ReviewLane,
    Signals,
    Skill,
    Tier,
)

THRESHOLD_USD = 10_000
# The 8 states Michael named plus the 4 the extract shows behaving the same way
# (review_floor.py section 2): every claim over $10K flagged, none at or under.
NAMED_STATES = frozenset({"CA", "NY", "NJ", "FL", "IL", "PA", "OH", "GA"})
RULE_STATES = NAMED_STATES | {"MA", "MD", "MI", "VA"}

REVIEW_LANES: frozenset[ReviewLane] = frozenset(
    {"standard_review", "regulatory_review", "senior_review"}
)
BASE_TIER: dict[Complexity, Tier] = {"Simple": Tier.T1, "Moderate": Tier.T2, "Complex": Tier.T3}
LANE_WORDS: dict[ReviewLane, str] = {
    "fast_lane": "fast lane",
    "standard_review": "standard review",
    "regulatory_review": "regulatory review",
    "senior_review": "senior review",
}


def over_threshold_in_rule_state(claim: Claim) -> bool:
    return claim.state in RULE_STATES and claim.claim_amount_usd > THRESHOLD_USD


def regulatory_check(claim: Claim) -> Regulation:
    """Route on both flags: the regulation label, the stated rule, or the review flag.

    The label alone is not trusted to be complete (section 9 finds rule claims without
    it), and the review flag alone misses 437 labeled claims (section 6).
    """
    by_rule = over_threshold_in_rule_state(claim)
    labeled = claim.requires_human_by_regulation == "Yes"
    flagged = claim.flagged_for_human_review == "Yes"
    regulated = labeled or by_rule
    reason = None
    if by_rule:
        reason = f"regulated ({claim.state}, over $10K)"
    elif labeled:
        reason = "regulated — rule unknown"
    elif flagged:
        reason = "flagged for review"
    return Regulation(regulated=regulated, by_rule=by_rule, flagged=flagged, reason=reason)


TIERS = list(Tier)


def classify(claim: Claim, signals: Signals) -> tuple[list[Skill], Tier]:
    skills = list(dict.fromkeys([claim.claim_type, *signals.secondary_skills]))
    tier = BASE_TIER[claim.complexity]
    if claim.claim_type == Skill.BODILY_INJURY and over_threshold_in_rule_state(claim):
        tier = Tier.T3
    elif signals.injury and tier == Tier.T1:
        tier = Tier.T2
    # The LLM's tier suggestion can only raise the tier, never lower it.
    if signals.suggested_tier and TIERS.index(signals.suggested_tier) > TIERS.index(tier):
        tier = signals.suggested_tier
    return skills, tier


def review_lane(tier: Tier, regulation: Regulation, attention: list[AttentionItem]) -> ReviewLane:
    """Fast lane is one-click confirm by a person, never automatic; everything else is review."""
    if tier == Tier.T3:
        return "senior_review"
    if regulation.regulated:
        return "regulatory_review"
    if regulation.flagged or attention or tier != Tier.T1:
        return "standard_review"
    return "fast_lane"


def routing_reason(
    claim: Claim,
    tier: Tier,
    lane: ReviewLane,
    regulation: Regulation,
    attention: list[AttentionItem],
) -> str:
    kind = claim.claim_type.value.lower()
    if regulation.regulated and not regulation.flagged:
        where = (
            f"{claim.state}, over $10K" if regulation.by_rule else f"{claim.state}, rule unknown"
        )
        return f"Regulated ({where}): required review was missing; added"
    if claim.claim_type == Skill.BODILY_INJURY and tier == Tier.T3 and regulation.by_rule:
        if claim.intake_channel == "Fax/EDI" and attention:
            return f"BI over $10K in {claim.state}, messy fax/EDI intake → T3 senior"
        return f"BI over $10K in {claim.state} → T3 senior first"
    if lane == "fast_lane":
        complete = "complete at intake" if claim.details.get("complete_at_intake") else "no flags"
        return f"Simple {kind}, {complete} → T1 fast lane"
    why = f"{claim.complexity} {kind}"
    if regulation.reason:
        why = f"{why}, {regulation.reason}"
    if attention:
        why = f"{why}, {len(attention)} intake item(s) to check"
    return f"{why} → {tier} {TIER_LABELS[tier]}, {LANE_WORDS[lane]}"


def priority_key(claim: Claim, tier: Tier, regulation: Regulation, now: datetime) -> tuple:
    """SLA time left first (breached sorts first), then claims a person must see, then tier."""
    return (claim.sla_due_at - now, not regulation.review_required, tier)
