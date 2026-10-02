"""Load and validate the demo fixtures in demo/data/ and the extract in reference/."""

import csv
import json
from collections.abc import Iterator
from datetime import datetime
from functools import cache
from pathlib import Path

from models import Adjuster, Claim, ClaimFixture, LearningHistory

DATA = Path(__file__).resolve().parent.parent / "data"
REPO = DATA.parents[1]
EXTRACT = REPO / "reference" / "claims_processing.csv"


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


def extract_rows() -> Iterator[dict[str, str | None]]:
    """Raw extract rows, blanks as None; validate with `claim_from_row`."""
    with EXTRACT.open(newline="") as f:
        for row in csv.DictReader(f):
            yield {k: v or None for k, v in row.items()}


def claim_from_row(row: dict[str, str | None]) -> Claim:
    """The extract has no receipt time, so a claim counts as received at the start of its day."""
    filed = row.get("filed_date")
    try:
        received = datetime.fromisoformat(filed) if filed else None
    except ValueError:
        received = None  # Claim validation then names filed_date and received_at
    return Claim.model_validate({**row, "received_at": received})
