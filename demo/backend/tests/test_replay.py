"""Replay runner (#5): seeded schedule, real pipeline outcomes, controls and the SSE feed."""

import asyncio
import itertools
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import clock
from app import app, render_card
from clock import DEMO_START
from fixtures import load_claim_fixtures
from models import Stage
from replay import Replay, arrivals, events, runner, schedule

FIXTURES = set(load_claim_fixtures())
FIRST = 1500  # events: a little over three simulated days


# How the admin page calls the controls: the board's CSRF header, with ?view=admin.
ADMIN = {"headers": {"X-Meridian-Board": "1"}}


def _admin_client(**kwargs) -> TestClient:
    return TestClient(app, headers=ADMIN["headers"], **kwargs)


def _key(s):
    return (s.event.claim_id, s.event.stage, s.at, s.event.payload)


@pytest.fixture(scope="module")
def first_events():
    return list(itertools.islice(events(), FIRST))


@pytest.fixture
def replay():
    r = app.state.replay
    r.restart()
    yield r
    r.set(speed=runner.DEFAULT_SPEED, paused=False)
    r.restart(schedule.SEED)


def _frames(text: str) -> list[tuple[str, dict]]:
    frames = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append((lines["event"], json.loads(lines["data"])))
    return frames


# --- Schedule ---


def test_same_seed_same_sequence(first_events):
    assert [_key(s) for s in itertools.islice(events(), FIRST)] == [_key(s) for s in first_events]


def test_different_seed_different_sequence(first_events):
    other = list(itertools.islice(events(seed=schedule.SEED + 1), FIRST))
    assert [_key(s) for s in other] != [_key(s) for s in first_events]


def test_events_are_in_time_order_on_the_demo_clock(first_events):
    times = [s.at for s in first_events]
    assert times == sorted(times)
    assert times[0] >= DEMO_START
    assert all(s.event.timestamp == s.at for s in first_events)


def test_arrivals_follow_filed_date_order():
    extract = [a for a in itertools.islice(arrivals(), 400) if a.claim_id not in FIXTURES]
    assert [a.at for a in extract] == sorted(a.at for a in extract)
    for a in extract:
        if not a.dropped:
            assert a.claim.received_at == a.at  # type: ignore[union-attr]


def test_fixtures_arrive_within_the_first_minute_at_default_speed(first_events):
    minute = timedelta(hours=60 * runner.DEFAULT_SPEED)
    received = {s.event.claim_id for s in first_events if s.at - DEMO_START < minute}
    assert received >= FIXTURES
    # Each is routed, as its fixture expects, and keeps its SLA story.
    expected = load_claim_fixtures()
    done = {s.event.claim_id: s for s in first_events if s.event.stage is Stage.PRIORITIZED}
    for claim_id, fx in expected.items():
        p = done[claim_id].event.payload
        assert p["tier"] == fx.expected.tier
        assert p["sla"] == fx.expected.sla_in_demo, claim_id


def test_fixtures_appear_only_once(first_events):
    received = [s.event.claim_id for s in first_events if s.event.stage is Stage.RECEIVED]
    for claim_id in FIXTURES:
        assert received.count(claim_id) == 1


def test_exceptions_come_from_the_real_pipeline(first_events):
    stops = [s.event for s in first_events if s.event.stage is Stage.EXCEPTION]
    assert {e.payload["reason"] for e in stops} == {"failed_write", "missing_fields"}
    for e in stops:
        assert e.payload["issues"]
        assert e.claim_id not in FIXTURES  # demo claims keep their stories


def test_a_claims_events_are_spread_so_its_card_moves(first_events):
    claim_id = next(iter(FIXTURES))
    times = [s.at for s in first_events if s.event.claim_id == claim_id]
    assert len(set(times)) == len(times)


# --- Runner ---


def test_step_advances_the_demo_clock(replay):
    s = replay.step()
    assert s is not None
    assert clock.now() == s.at == replay.sim_now


def test_restart_resets_board_and_clock(replay):
    for _ in range(50):
        replay.step()
    replay.restart()
    assert clock.now() == DEMO_START
    assert replay.board.claims == {}
    first = replay.step()
    assert first is not None
    assert _key(first) == _key(next(events()))


def test_board_retires_old_cards_but_never_demo_claims(monkeypatch, replay):
    monkeypatch.setattr(runner, "MAX_DONE", 3)
    for _ in range(600):
        replay.step()
    done = [v for v in replay.board.claims.values() if v.stage is Stage.WITH_ADJUSTER]
    assert len([v for v in done if not v.pinned]) == 3
    assert {v.claim_id for v in done} >= FIXTURES


def test_paused_runner_plays_nothing_and_resumes():
    async def scenario():
        r = Replay(render_card)
        r.set(speed=1000, paused=True)
        r.start()
        await asyncio.sleep(0.2)
        assert r.board.claims == {}
        r.set(paused=False)
        for _ in range(100):
            await asyncio.sleep(0.05)
            if r.board.claims:
                break
        await r.stop()
        assert r.board.claims

    asyncio.run(scenario())
    clock.reset()


def test_runner_plays_the_same_sequence_as_the_schedule():
    async def scenario():
        r = Replay(render_card)
        r.set(speed=10_000)
        q: list[str] = []

        async def watch():
            async for text in r.stream(limit=40):
                q.append(text)

        watcher = asyncio.create_task(watch())
        await asyncio.sleep(0)
        r.start()
        await asyncio.wait_for(watcher, 10)
        await r.stop()
        return q

    frames = _frames("".join(asyncio.run(scenario())))
    clock.reset()
    played = [(d["claim_id"], d["stage"]) for name, d in frames if name == "claim"]
    expected = [(s.event.claim_id, str(s.event.stage)) for s in itertools.islice(events(), 40)]
    assert played == expected


# --- API ---


def test_controls_round_trip_and_validate(replay):
    client = _admin_client()
    assert client.get("/api/replay").json()["seed"] == schedule.SEED
    status = client.post("/api/replay?view=admin", json={"speed": 4, "paused": True}).json()
    assert (status["speed"], status["paused"]) == (4, True)
    assert client.get("/api/replay").json()["paused"] is True
    assert client.post("/api/replay?view=admin", json={"paused": False}).json()["speed"] == 4
    for bad in ({"speed": 0}, {"speed": 49}, {"paused": "later"}):
        assert client.post("/api/replay?view=admin", json=bad).status_code == 422


def test_restart_endpoint_takes_a_seed(replay):
    client = _admin_client()
    assert client.post("/api/replay/restart?view=admin", json={"seed": 7}).json()["seed"] == 7
    assert client.post("/api/replay/restart?view=admin").json()["seed"] == 7
    assert (
        client.post("/api/replay/restart?view=admin", json={"seed": schedule.SEED}).json()["seed"]
        == schedule.SEED
    )


def test_new_viewer_gets_reset_status_and_the_board_so_far(replay):
    for _ in range(30):
        replay.step()
    on_board = list(replay.board.claims)
    response = TestClient(app).get(f"/api/events?limit={len(on_board)}")
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = _frames(response.text)
    assert frames[0] == ("reset", {"counters": replay.board.counters()})
    assert frames[1][0] == "control" and frames[1][1]["seed"] == schedule.SEED
    claims = [d for name, d in frames if name == "claim"]
    assert [d["claim_id"] for d in claims] == on_board
    card = claims[0]
    assert f'id="card-{card["claim_id"]}"' in card["html"]
    assert card["counters"] == replay.board.counters()


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/replay?view=admin", {}),  # no CSRF header: a cross-site form or fetch
        ("/api/replay/restart?view=admin", {}),
        ("/api/replay?view=manager", ADMIN["headers"]),
        ("/api/replay/restart?view=manager", ADMIN["headers"]),
        ("/api/replay/restart", ADMIN["headers"]),  # no view means no admin
    ],
)
def test_controls_refuse_unguarded_and_manager_calls(replay, path, headers):
    replay.step()
    board = list(replay.board.claims)
    body = {"paused": True, "seed": schedule.SEED + 2}  # each route reads its own field
    response = TestClient(app).post(path, json=body, headers=headers)
    assert response.status_code == 403
    assert replay.paused is False
    assert replay.seed == schedule.SEED
    assert list(replay.board.claims) == board  # not restarted


def test_admin_page_script_sends_the_control_guards():
    # No JS test harness here: check the one function every control goes through.
    script = (Path(__file__).parents[1] / "static" / "admin.js").read_text()
    post = script[
        script.index("const post = ") : script.index("});", script.index("const post = "))
    ]
    assert "?view=admin" in post
    assert '"X-Meridian-Board": "1"' in post


def test_event_stream_rejects_out_of_range_limit():
    assert TestClient(app).get("/api/events?limit=0").status_code == 422


def test_server_plays_the_feed_on_startup():
    with _admin_client() as client:
        client.post("/api/replay?view=admin", json={"speed": 48})
        try:
            frames = _frames(client.get("/api/events?limit=5").text)
        finally:
            client.post("/api/replay?view=admin", json={"speed": runner.DEFAULT_SPEED})
            client.post("/api/replay/restart?view=admin")
    assert [name for name, _ in frames].count("claim") == 5


def test_dropped_rows_are_fax_edi_with_a_field_missing_and_no_outage():
    dropped = [a for a in itertools.islice(arrivals(), 1500) if a.dropped]
    assert dropped
    for a in dropped:
        row = a.claim
        assert isinstance(row, dict)
        assert row["intake_channel"] == "Fax/EDI"
        assert any(row[f] is None for f in schedule.DROPPABLE)
        assert not a.outage


def test_replay_loops_to_the_start_when_the_extract_ends(monkeypatch):
    short = list(itertools.islice(events(), 3))
    monkeypatch.setattr(schedule, "events", lambda seed=schedule.SEED: iter(short))

    async def scenario():
        r = Replay(render_card)
        r.set(speed=10_000)
        frames: list[str] = []

        async def watch():
            async for text in r.stream(limit=5):
                frames.append(text)

        watcher = asyncio.create_task(watch())
        await asyncio.sleep(0)
        r.start()
        await asyncio.wait_for(watcher, 10)
        await r.stop()
        return frames

    frames = _frames("".join(asyncio.run(scenario())))
    clock.reset()
    names = [name for name, _ in frames if name in ("claim", "reset")]
    assert names == ["reset", "claim", "claim", "claim", "reset", "claim", "claim"]


def test_restart_during_a_fetch_drops_the_stale_event(monkeypatch):
    async def scenario():
        r = Replay(render_card)
        stale_pass = r._events
        real_next = next

        def slow_next(it, default):
            if it is stale_pass:
                r.restart(schedule.SEED + 1)  # lands while the old pass is fetching
            return real_next(it, default)

        monkeypatch.setattr(
            runner.asyncio, "to_thread", lambda f, *a: asyncio.sleep(0, slow_next(*a))
        )
        r.set(speed=10_000)
        r.start()
        for _ in range(100):
            await asyncio.sleep(0.01)
            if r.board.claims:
                break
        await r.stop()
        return r

    r = asyncio.run(scenario())
    clock.reset()
    first = next(iter(r.board.claims.values())).trace[0]
    assert first == next(events(schedule.SEED + 1)).event
    assert first != next(events()).event
