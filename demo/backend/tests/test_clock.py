import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import clock
from fixtures import load_claim_fixtures

BACKEND = Path(__file__).resolve().parents[1]

# No call parens required, so default_factory=datetime.now is caught too.
WALL_CLOCK = re.compile(
    r"\bdatetime\.(now|utcnow|today)\b|\bdate\.today\b"
    r"|\btime\.(time|time_ns|monotonic)\b|\bfrom time import\b"
)


@pytest.fixture(autouse=True)
def reset_clock():
    yield
    clock.reset()


@pytest.mark.parametrize("claim_id", sorted(load_claim_fixtures()))
def test_fixture_shows_expected_sla_state_at_default_clock(claim_id):
    fixture = load_claim_fixtures()[claim_id]
    assert fixture.claim.sla_state(clock.now()) == fixture.expected.sla_in_demo


def test_fixtures_cover_every_sla_state():
    states = {f.expected.sla_in_demo for f in load_claim_fixtures().values()}
    assert states == {"on_track", "at_risk", "breached"}


def test_advance_moves_the_clock_forward():
    assert clock.advance(timedelta(hours=2)) == clock.DEMO_START + timedelta(hours=2)
    assert clock.now() == clock.DEMO_START + timedelta(hours=2)


def test_advancing_a_day_breaches_an_on_track_claim():
    claim = load_claim_fixtures()["IS-CLM-2025000300"].claim
    assert claim.sla_state(clock.now()) == "on_track"
    clock.advance(timedelta(hours=24))
    assert claim.sla_state(clock.now()) == "breached"


def test_reset_restores_demo_start():
    clock.advance(timedelta(days=3))
    clock.reset()
    assert clock.now() == clock.DEMO_START


def test_reset_can_pin_another_instant():
    at = datetime(2025, 10, 16, 9, 0)
    clock.reset(at)
    assert clock.now() == at


def test_sla_state_boundaries():
    claim = load_claim_fixtures()["IS-CLM-2025000300"].claim
    due = claim.sla_due_at
    assert claim.sla_state(due - timedelta(hours=6, seconds=1)) == "on_track"
    assert claim.sla_state(due - timedelta(hours=6)) == "on_track"
    assert claim.sla_state(due - timedelta(hours=5, minutes=59)) == "at_risk"
    assert claim.sla_state(due - timedelta(seconds=1)) == "at_risk"
    assert claim.sla_state(due) == "breached"


def test_no_backend_code_reads_the_wall_clock():
    offenders = [
        str(p.relative_to(BACKEND))
        for p in BACKEND.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts and WALL_CLOCK.search(p.read_text())
    ]
    assert offenders == []


@pytest.mark.parametrize(
    ("source", "reads_wall_clock"),
    [
        ("datetime.now()", True),
        ("datetime.utcnow()", True),
        ("Field(default_factory=datetime.now)", True),
        ("date.today()", True),
        ("time.time_ns()", True),
        ("from time import monotonic", True),
        ("clock.now()", False),
        ("def now() -> datetime:", False),
    ],
)
def test_wall_clock_pattern(source, reads_wall_clock):
    assert bool(WALL_CLOCK.search(source)) == reads_wall_clock
