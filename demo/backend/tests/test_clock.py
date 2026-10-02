import re
from datetime import timedelta
from pathlib import Path

import pytest

import clock
from fixtures import load_claim_fixtures

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def reset_clock():
    yield
    clock.reset()


@pytest.mark.parametrize("claim_id", sorted(load_claim_fixtures()))
def test_fixture_shows_expected_sla_state_at_default_clock(claim_id):
    fixture = load_claim_fixtures()[claim_id]
    assert fixture.claim.sla_state(clock.now()) == fixture.expected.sla_in_demo


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


def test_sla_state_boundaries():
    claim = load_claim_fixtures()["IS-CLM-2025000300"].claim
    due = claim.sla_due_at
    assert claim.sla_state(due - timedelta(hours=6, seconds=1)) == "on_track"
    assert claim.sla_state(due - timedelta(hours=6)) == "on_track"
    assert claim.sla_state(due - timedelta(hours=5, minutes=59)) == "at_risk"
    assert claim.sla_state(due - timedelta(seconds=1)) == "at_risk"
    assert claim.sla_state(due) == "breached"


def test_no_backend_code_reads_the_wall_clock():
    wall_clock = re.compile(r"datetime\.now\(|utcnow\(|time\.time\(|date\.today\(")
    offenders = [
        str(p.relative_to(BACKEND))
        for p in BACKEND.rglob("*.py")
        if ".venv" not in p.parts and "tests" not in p.parts and wall_clock.search(p.read_text())
    ]
    assert offenders == []
