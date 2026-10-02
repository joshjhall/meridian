"""Load and validate the demo fixtures in demo/data/."""

import json
from functools import cache
from pathlib import Path

from models import Adjuster, ClaimFixture, LearningHistory

DATA = Path(__file__).resolve().parent.parent / "data"


@cache
def load_claim_fixtures() -> dict[str, ClaimFixture]:
    fixtures = (
        ClaimFixture.model_validate_json(p.read_text())
        for p in sorted((DATA / "claims").glob("*.json"))
    )
    return {f.claim.claim_id: f for f in fixtures}


@cache
def load_roster() -> list[Adjuster]:
    return [Adjuster.model_validate(a) for a in json.loads((DATA / "roster.json").read_text())]


@cache
def load_history() -> LearningHistory:
    return LearningHistory.model_validate_json((DATA / "history.json").read_text())
