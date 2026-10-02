"""Admin queues board (#7): the board, manual moves, write status, fault toggle, guards."""

import random
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import clock
import queues
from app import app, templates, transfer_runner
from claimspro_sim import ClaimsProSim, FaultConfig
from claimspro_sim.api import get_sim
from fixtures import load_roster
from models import Tier

SIMPLE = "IS-CLM-2025000300"  # FL, under $10K, T1: not regulated
REGULATED_T2 = "IS-CLM-2025000375"  # GA, over $10K, T2
REGULATED_T3 = "IS-CLM-2025004222"  # NY bodily injury, T3

ROSTER = {a.id: a for a in load_roster()}


def adjuster(tier: Tier, *, role: str | None = None, only: bool = False, skip: str = "") -> str:
    """An adjuster holding `tier` (as their highest with `only`), optionally of one role."""
    for a in ROSTER.values():
        holds = queues.top_tier(a) is tier if only else tier in a.tiers
        if holds and (role is None or a.role == role) and a.id != skip:
            return a.id
    raise LookupError(tier)


@pytest.fixture(autouse=True)
def _clock():
    clock.reset()
    yield
    clock.reset()


@pytest.fixture
def sim() -> ClaimsProSim:
    return ClaimsProSim(sleep=lambda _s: None, now=clock.now, rng=random.Random(7))


@pytest.fixture
def client(sim: ClaimsProSim):
    app.dependency_overrides[get_sim] = lambda: sim
    # Run each write inline, so the response already reflects its outcome.
    app.dependency_overrides[transfer_runner] = lambda: lambda job: job()
    yield TestClient(app)
    app.dependency_overrides.clear()


def owner(sim: ClaimsProSim, claim_id: str) -> str:
    claim = sim.store.get(claim_id)
    assert claim is not None
    return claim.adjuster_id


def transfer(client: TestClient, claim_id: str, to: str, view: str = "admin"):
    return client.post(f"/admin/queues/claims/{claim_id}/transfer", params={"to": to, "view": view})


# --- The board ---


def test_board_shows_all_95_adjusters_grouped_by_top_tier(client: TestClient):
    html = client.get("/admin/queues").text
    assert html.count("data-queue=") == len(ROSTER) == 95
    # Senior first, then down the tiers; counts from the seeded roster (README).
    headings = re.findall(r'id="tier-(T\d)"', html)
    assert headings == ["T3", "T2", "T1"]
    assert re.search(r"T3 · senior\s*<span[^>]*>16 adjusters", html)
    assert re.search(r"T2 · involved\s*<span[^>]*>42 adjusters", html)
    assert re.search(r"T1 · standard\s*<span[^>]*>37 adjusters", html)
    assert html.count("data-load>") == 95


def test_every_open_claim_sits_in_its_adjusters_queue(sim: ClaimsProSim):
    groups = queues.board(sim, clock.now())
    placed = {qc.claim.claim_id: q.adjuster.id for g in groups for q in g.queues for qc in q.claims}
    assert placed == {c.claim_id: c.adjuster_id for c in sim.store.list_claims()}


def test_claims_are_ordered_by_sla_time_left(sim: ClaimsProSim):
    for g in queues.board(sim, clock.now()):
        for q in g.queues:
            lefts = [qc.left for qc in q.claims]
            assert lefts == sorted(lefts)


def test_load_moves_with_a_transfer(client: TestClient, sim: ClaimsProSim):
    to = adjuster(Tier.T1, skip=owner(sim, SIMPLE))
    before = {q.adjuster.id: q.load for g in queues.board(sim, clock.now()) for q in g.queues}
    src = owner(sim, SIMPLE)
    transfer(client, SIMPLE, to)
    after = {q.adjuster.id: q.load for g in queues.board(sim, clock.now()) for q in g.queues}
    assert after[to] == before[to] + 1
    assert after[src] == max(0, before[src] - 1)


@pytest.mark.parametrize(
    ("left", "text"),
    [
        (timedelta(hours=5, minutes=20), "5h 20m left"),
        (timedelta(days=1, hours=2), "1d 2h left"),
        (timedelta(0), "breached 0h 0m ago"),
        (timedelta(days=-2, hours=-3), "breached 2d 3h ago"),
    ],
)
def test_format_left(left: timedelta, text: str):
    assert queues.format_left(left) == text


def test_sla_time_left_follows_the_demo_clock(sim: ClaimsProSim):
    def left_of(claim_id: str) -> timedelta:
        groups = queues.board(sim, clock.now())
        return next(
            qc.left
            for g in groups
            for q in g.queues
            for qc in q.claims
            if qc.claim.claim_id == claim_id
        )

    before = left_of(SIMPLE)
    clock.advance(timedelta(hours=2))
    assert left_of(SIMPLE) == before - timedelta(hours=2)


# --- Moves and write status ---


def test_transfer_confirms_and_moves_the_claim(client: TestClient, sim: ClaimsProSim):
    to = adjuster(Tier.T1, skip=owner(sim, SIMPLE))
    res = transfer(client, SIMPLE, to)
    assert res.status_code == 200
    assert 'data-write-status="confirmed"' in res.text
    assert "Confirmed in ClaimsPro" in res.text
    assert owner(sim, SIMPLE) == to
    statuses = [e.payload["write_status"] for e in sim.events(SIMPLE)]
    assert statuses == ["pending", "confirmed"]


def test_status_chip_polls_while_the_write_is_pending(client: TestClient, sim: ClaimsProSim):
    to = adjuster(Tier.T1, skip=owner(sim, SIMPLE))
    app.dependency_overrides[transfer_runner] = lambda: lambda _job: None  # never runs
    res = transfer(client, SIMPLE, to)
    assert "Pending in ClaimsPro" in res.text
    key = re.search(r"key=([0-9a-f-]+)", res.text)
    assert key is not None
    poll = client.get(f"/admin/queues/claims/{SIMPLE}/write-status", params={"key": key[1]})
    assert 'hx-trigger="load delay:500ms"' in poll.text


def test_settled_chip_stops_polling(client: TestClient, sim: ClaimsProSim):
    res = transfer(client, SIMPLE, adjuster(Tier.T1, skip=owner(sim, SIMPLE)))
    assert "hx-trigger" not in res.text


def test_status_belongs_to_one_move(client: TestClient, sim: ClaimsProSim):
    transfer(client, SIMPLE, adjuster(Tier.T1, skip=owner(sim, SIMPLE)))
    # A different key (a later move) has not reported yet, whatever the claim's history.
    assert queues.write_progress(sim, SIMPLE, "another-move")["write_status"] == "pending"


def test_fault_toggle_shows_retries_then_failure_with_alert(client: TestClient, sim: ClaimsProSim):
    src = owner(sim, SIMPLE)
    on = client.post("/admin/queues/faults", params={"on": True})
    assert on.json() == {"on": True}
    res = transfer(client, SIMPLE, adjuster(Tier.T1, skip=src))
    assert 'data-write-status="failed"' in res.text
    assert "Failed after 3 attempts. Engineering and client IT notified." in res.text
    assert owner(sim, SIMPLE) == src
    statuses = [e.payload["write_status"] for e in sim.events(SIMPLE)]
    assert statuses == ["pending", "retrying", "retrying", "failed"]
    [alert] = sim.alerts()
    assert alert.operation == "TransferWorkItem"

    assert client.post("/admin/queues/faults", params={"on": False}).json() == {"on": False}
    assert (
        'data-write-status="confirmed"'
        in transfer(client, SIMPLE, adjuster(Tier.T1, skip=src)).text
    )


def test_fault_toggle_off_keeps_other_faults(client: TestClient, sim: ClaimsProSim):
    sim.faults.set({"AddNote": FaultConfig(failure_rate=0.5)})
    client.post("/admin/queues/faults", params={"on": True})
    client.post("/admin/queues/faults", params={"on": False})
    assert set(sim.faults.configs()) == {"AddNote"}


def test_retrying_chip_counts_attempts():
    html = templates.get_template("admin/_write_status.html").render(
        claim_id=SIMPLE,
        key="k",
        viewer="admin",
        progress={"write_status": "retrying", "attempt": 2},
        max_attempts=3,
    )
    assert "Retrying (2 of 3 failed)" in html
    assert "hx-trigger" in html


# --- Guards ---


def test_regulated_claim_blocked_from_adjuster_without_its_tier(
    client: TestClient, sim: ClaimsProSim
):
    src = owner(sim, REGULATED_T2)
    to = adjuster(Tier.T1, only=True)
    res = transfer(client, REGULATED_T2, to)
    assert res.status_code == 409
    assert "Move blocked" in res.text
    assert f"has no {Tier.T2} review lane" in res.text
    assert owner(sim, REGULATED_T2) == src
    assert sim.events(REGULATED_T2) == []


def test_regulated_non_t3_claim_moves_to_any_adjuster_with_its_tier(
    client: TestClient, sim: ClaimsProSim
):
    # #3 routes these to regulatory_review with any adjuster holding the tier, not only seniors.
    to = adjuster(Tier.T2, role="adjuster", skip=owner(sim, REGULATED_T2))
    res = transfer(client, REGULATED_T2, to)
    assert res.status_code == 200
    assert owner(sim, REGULATED_T2) == to


def test_regulated_t3_claim_needs_a_senior_or_lead(client: TestClient, sim: ClaimsProSim):
    assert transfer(client, REGULATED_T3, adjuster(Tier.T2, only=True)).status_code == 409
    to = adjuster(Tier.T3, role="senior", skip=owner(sim, REGULATED_T3))
    assert transfer(client, REGULATED_T3, to).status_code == 200
    assert owner(sim, REGULATED_T3) == to


def test_block_reason_requires_role_for_t3(sim: ClaimsProSim):
    claim = sim.store.get(REGULATED_T3)
    assert claim is not None
    senior = ROSTER[adjuster(Tier.T3, role="senior", skip=claim.adjuster_id)]
    t3_adjuster = senior.model_copy(update={"role": "adjuster"})
    assert queues.block_reason(claim, senior) is None
    assert "senior or lead reviewer" in (queues.block_reason(claim, t3_adjuster) or "")


def test_regulated_claim_without_a_tier_is_held_to_t3(sim: ClaimsProSim):
    base = sim.store.get(SIMPLE)
    assert base is not None
    # Not a fixture ID, so no expected tier to fall back on.
    claim = base.model_copy(
        update={
            "claim_id": "IS-CLM-9999999999",
            "tier": None,
            "requires_human_by_regulation": "Yes",
        }
    )
    assert queues.claim_tier(claim) is None
    assert queues.review_tier(claim) is Tier.T3
    t2 = ROSTER[adjuster(Tier.T2, only=True, skip=claim.adjuster_id)]
    senior = ROSTER[adjuster(Tier.T3, role="senior", skip=claim.adjuster_id)]
    assert "no T3 review lane" in (queues.block_reason(claim, t2) or "")
    assert queues.block_reason(claim, senior) is None


@pytest.mark.parametrize(
    ("flag", "state", "amount", "regulated"),
    [
        ("Yes", "TN", 500.0, True),  # the regulation flag alone is enough
        ("No", "CA", 10_000.0, False),  # over $10K means strictly over
        ("No", "CA", 10_000.01, True),
        ("No", "TN", 90_000.0, False),  # not a named state
    ],
)
def test_is_regulated(sim: ClaimsProSim, flag: str, state: str, amount: float, regulated: bool):
    base = sim.store.get(SIMPLE)
    assert base is not None
    claim = base.model_copy(
        update={"requires_human_by_regulation": flag, "state": state, "claim_amount_usd": amount}
    )
    assert queues.is_regulated(claim) is regulated


def test_second_move_is_blocked_while_the_first_is_in_flight(client: TestClient, sim: ClaimsProSim):
    held: list = []
    app.dependency_overrides[transfer_runner] = lambda: held.append  # job waits until we run it
    src = owner(sim, SIMPLE)
    first = transfer(client, SIMPLE, adjuster(Tier.T1, skip=src))
    assert first.status_code == 200
    second = transfer(client, SIMPLE, adjuster(Tier.T2, skip=src))
    assert second.status_code == 409
    assert "still in flight" in second.text
    assert len(held) == 1

    held.pop()()  # the first write settles and frees the claim
    assert transfer(client, SIMPLE, src).status_code == 200


def test_pending_write_status_blocks_a_move(sim: ClaimsProSim):
    claim = sim.store.get(SIMPLE)
    assert claim is not None
    claim.write_status = "pending"
    reason = queues.block_reason(claim, ROSTER[adjuster(Tier.T1, skip=claim.adjuster_id)])
    assert reason is not None and "still in flight" in reason


def test_unknown_adjuster_and_same_queue_are_blocked(client: TestClient, sim: ClaimsProSim):
    assert "Unknown adjuster" in transfer(client, SIMPLE, "ADJ-999").text
    assert "Already in" in transfer(client, SIMPLE, owner(sim, SIMPLE)).text
    assert transfer(client, "IS-CLM-0000000000", "ADJ-101").status_code == 404


def test_fault_toggle_is_admin_only(client: TestClient, sim: ClaimsProSim):
    res = client.post("/admin/queues/faults", params={"on": True, "view": "manager"})
    assert res.status_code == 403
    assert sim.faults.configs() == {}
    assert 'id="fault-toggle"' not in client.get("/admin/queues", params={"view": "manager"}).text
    assert 'id="fault-toggle"' in client.get("/admin/queues").text


def test_managers_can_move_work(client: TestClient, sim: ClaimsProSim):
    to = adjuster(Tier.T1, skip=owner(sim, SIMPLE))
    assert transfer(client, SIMPLE, to, view="manager").status_code == 200
