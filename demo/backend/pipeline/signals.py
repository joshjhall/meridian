"""Complexity signals: the one step an LLM fills (#4).

Pipeline runs (batch and replay) read the recorded response for each demo claim, so
they never wait on a network call; the live call runs on demand for one claim
(`llm_signals.run_live`). Both go through the same schema and quote checks, and only
verified signals reach routing.
"""

from models import Claim, Signals
from pipeline import llm_signals
from pipeline.llm_signals import PROMPT_VERSION

__all__ = ["PROMPT_VERSION", "complexity_signals"]


def complexity_signals(claim: Claim) -> Signals:
    """Recorded signals for a demo claim, checked like live ones; an empty signal otherwise."""
    return llm_signals.from_recorded(claim)
