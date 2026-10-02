"""Match a routed claim to an adjuster: skills and tier first, then the lightest load."""

from collections.abc import Iterable

from models import Adjuster, ReviewLane, Skill, Tier
from pipeline.rules import REVIEW_LANES

SENIOR_ROLES = frozenset({"senior", "lead"})


class Loads:
    """Current load per adjuster, raised as the batch assigns so work spreads out."""

    def __init__(self, roster: Iterable[Adjuster]) -> None:
        self.roster = list(roster)
        self._load = {a.id: a.current_load for a in self.roster}

    def __getitem__(self, adjuster_id: str) -> int:
        return self._load[adjuster_id]

    def take(self, adjuster_id: str) -> None:
        self._load[adjuster_id] += 1

    def release(self, adjuster_id: str) -> None:
        """A claim that stopped for a person after matching never reached this adjuster."""
        self._load[adjuster_id] -= 1


def match(
    skills: list[Skill], tier: Tier, lane: ReviewLane, loads: Loads
) -> tuple[Adjuster | None, str]:
    """The adjuster and how they matched; no adjuster means a person routes it by hand."""

    def eligible(a: Adjuster, needed: list[Skill]) -> bool:
        senior_ok = lane != "senior_review" or a.role in SENIOR_ROLES
        return tier in a.tiers and senior_ok and all(s in a.skills for s in needed)

    for needed, how in ((skills, "all skills"), (skills[:1], "primary skill only")):
        candidates = [a for a in loads.roster if eligible(a, needed)]
        if candidates:
            best = min(candidates, key=lambda a: (loads[a.id], a.id))
            loads.take(best.id)
            return best, how
    return None, "no adjuster with the skill and tier"


def route_problems(
    *,
    skills: list[Skill],
    tier: Tier | None,
    lane: ReviewLane | None,
    review_required: bool,
    adjuster: Adjuster | None,
) -> list[str]:
    """Anything inconsistent fails safe to the exceptions lane."""
    problems = []
    if not skills:
        problems.append("no skills")
    if tier is None:
        problems.append("no tier")
    if lane is None:
        problems.append("no lane")
    elif review_required and lane not in REVIEW_LANES:
        problems.append(f"review required but routed to {lane}")
    if adjuster is None:
        problems.append("no adjuster")
    elif tier is not None and tier not in adjuster.tiers:
        problems.append(f"{adjuster.id} does not work {tier}")
    return problems
