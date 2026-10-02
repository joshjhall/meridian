"""Complexity signals: the one step an LLM will fill (#4).

Until #4 lands this returns recorded output for the six demo fixtures, read from
their panel examples, and an empty signal for everything else.
"""

from models import Claim, Signals, Skill

# The prompt #4 will send; matches the latest signals-prompt release in data/history.json.
PROMPT_VERSION = "signals-prompt v1.2"

RECORDED: dict[str, Signals] = {
    # Rear-end collision with a claimed injury: vehicle damage is a second skill.
    "IS-CLM-2025002993": Signals(
        secondary_skills=[Skill.COLLISION], injury=True, confidence=0.69, source="recorded"
    ),
    "IS-CLM-2025004222": Signals(injury=True, confidence=0.9, source="recorded"),
    # Disputed intersection collision: liability plus the vehicle damage.
    "IS-CLM-2025004518": Signals(
        secondary_skills=[Skill.COLLISION], confidence=0.85, source="recorded"
    ),
}


def complexity_signals(claim: Claim) -> Signals:
    """Stub hook: #4 replaces this body with the LLM call; the signature stays."""
    return RECORDED.get(claim.claim_id, Signals(source="rules"))
