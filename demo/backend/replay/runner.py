"""The replay player (#5): one shared feed per process, paced on the demo clock.

The sequence comes from `schedule.events(seed)`; the player only decides when each
event plays. Speed is simulated hours per wall-clock second. Pause stops the clock.
Neither changes what plays next, so a seeded rehearsal matches the live demo.

Every viewer watches the same feed: speed and pause are global, and a viewer that
connects mid-replay first gets a `reset` and the board as it stands, then the live
tail. The board is bounded so a long replay doesn't pile up cards; demo claims are
never retired.
"""

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import datetime, timedelta
from typing import Any

import monitor

import clock
from claimspro_sim import ClaimsProSim
from models import Stage
from replay import schedule

DEFAULT_SPEED = 1.0  # simulated hours per second
MAX_DONE = 30  # with-adjuster cards kept on the board
MAX_EXCEPTIONS = 8  # open exceptions kept on the board
QUEUE_FRAMES = 1000  # a viewer this far behind is dropped; its browser reconnects
TICK_S = 0.25  # the demo clock moves at least this often between events
# Concurrent feed viewers; GET /api/events turns away the rest. A demo-sized limit,
# not a defense: put a proxy in front if the demo leaves a trusted network.
MAX_VIEWERS = max(1, int(os.environ.get("REPLAY_MAX_VIEWERS", "50")))  # 0 would refuse everyone


def frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


_served: Replay | None = None


def serve(replay: Replay) -> None:
    """Make `replay` the one the app serves; app.py calls this once at import."""
    global _served
    _served = replay


def current_sim() -> ClaimsProSim:
    """The served replay's ClaimsPro for the current pass: its write log and alerts.

    Replaced on every restart, so read it per request rather than holding it.
    """
    if _served is None:
        raise RuntimeError("no replay is being served")
    return _served.sim


class Replay:
    def __init__(self, render_card: Callable[[monitor.ClaimView], str], seed: int = schedule.SEED):
        self.render_card = render_card
        self.speed = DEFAULT_SPEED
        self.paused = False
        self._subscribers: set[asyncio.Queue[str | None]] = set()
        self._resumed = asyncio.Event()
        self._resumed.set()
        self._woken = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.restart(seed)

    # --- Controls ---

    def restart(self, seed: int | None = None) -> None:
        """Back to the start of the sequence (same seed unless given) and the demo clock."""
        self.seed = self.seed if seed is None else seed
        self.board = monitor.MonitorState()
        self.sim = schedule.PassSim()
        self._events: Iterator[schedule.Scheduled] = schedule.events(self.seed, self.sim)
        self._next: schedule.Scheduled | None = None
        self.sim_now = clock.DEMO_START
        clock.reset()
        self._broadcast(frame("reset", {"counters": self.board.counters()}))
        self._broadcast_control()
        self._woken.set()

    def set(self, *, speed: float | None = None, paused: bool | None = None) -> None:
        if speed is not None:
            self.speed = speed
        if paused is not None:
            self.paused = paused
            if paused:
                self._resumed.clear()
            else:
                self._resumed.set()
        self._broadcast_control()
        self._woken.set()  # end the current tick so the rest of the gap uses the new speed

    def status(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "speed": self.speed,
            "paused": self.paused,
            "sim_now": self.sim_now.isoformat(),
        }

    # --- Playing ---

    def step(self) -> schedule.Scheduled | None:
        """Play the next event now, whatever its time; None when the replay is over."""
        s = self._peek()
        if s is None:
            return None
        self._next = None
        self._advance_to(s.at)
        view = self.board.apply(s.event)
        self._broadcast(self._claim_frame(view))
        self._retire()
        return s

    def _peek(self) -> schedule.Scheduled | None:
        if self._next is None:
            self._next = next(self._events, None)
        return self._next

    def _advance_to(self, at: datetime) -> None:
        if at > self.sim_now:
            clock.advance(at - self.sim_now)
            self.sim_now = at

    async def run(self) -> None:
        """Play forever: wait out each event's simulated gap at the current speed."""
        while True:
            await self._resumed.wait()
            events = self._events
            if self._next is None:
                # The pipeline runs a claim inside `next`; keep that off the event loop.
                s = await asyncio.to_thread(next, events, None)
                if events is not self._events:
                    continue  # restarted meanwhile; that event belongs to the old pass
                if s is None:
                    self.restart()  # end of the extract: loop the demo
                    continue
                self._next = s
            s = self._next
            self._woken.clear()
            gap = (s.at - self.sim_now) / timedelta(hours=1) / self.speed
            if gap > 0:
                speed = self.speed
                elapsed = await self._wait(min(gap, TICK_S))
                if self._events is not events or self._next is not s:
                    continue  # restarted while waiting
                # Time waited counts at the speed it was waited at, whatever woke us,
                # so the clock runs between events and a control change loses nothing.
                waited = timedelta(hours=elapsed * speed)
                self._advance_to(min(s.at, self.sim_now + waited))
                continue
            if not self.paused:
                self.step()

    async def _wait(self, timeout: float) -> float:
        """Wait up to `timeout` seconds or until woken; the seconds actually waited.

        The one place `run` reads the wall clock, so tests can drive it virtually.
        """
        loop = asyncio.get_running_loop()
        started = loop.time()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._woken.wait(), timeout)
        return loop.time() - started

    def start(self) -> None:
        if self._task is None:
            # Fresh events on the running loop: this Replay outlives any one loop
            # (it is built at import), and an asyncio.Event binds to the loop it waits on.
            self._resumed, self._woken = asyncio.Event(), asyncio.Event()
            if not self.paused:
                self._resumed.set()
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # --- Board ---

    def _retire(self) -> None:
        for stage, cap in ((Stage.WITH_ADJUSTER, MAX_DONE), (Stage.EXCEPTION, MAX_EXCEPTIONS)):
            # Claims dict order is first-seen order, so the oldest go first.
            ids = [cid for cid, v in self.board.claims.items() if v.stage is stage and not v.pinned]
            for claim_id in ids[: max(0, len(ids) - cap)]:
                del self.board.claims[claim_id]
                self._broadcast(
                    frame("remove", {"claim_id": claim_id, "counters": self.board.counters()})
                )

    def _claim_frame(self, view: monitor.ClaimView) -> str:
        return frame(
            "claim",
            {
                "claim_id": view.claim_id,
                "stage": str(view.stage),
                "html": self.render_card(view),
                "counters": self.board.counters(),
            },
        )

    # --- Viewers ---

    @property
    def viewers(self) -> int:
        return len(self._subscribers)

    def _broadcast(self, text: str) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(text)
            except asyncio.QueueFull:
                self._subscribers.discard(q)
                q.get_nowait()  # make room for the hang-up
                q.put_nowait(None)

    def _broadcast_control(self) -> None:
        self._broadcast(frame("control", self.status()))

    async def stream(self, limit: int | None = None) -> AsyncIterator[str]:
        """SSE for one viewer: reset, the board as it stands, then live frames.

        `limit` caps the number of `claim` frames, which tests use.
        """
        q: asyncio.Queue[str | None] = asyncio.Queue(QUEUE_FRAMES)
        # Snapshot and subscribe in one step: anything broadcast later is queued and
        # newer than the snapshot, so a card never steps backwards.
        board = [self._claim_frame(v) for v in self.board.claims.values()]
        reset = frame("reset", {"counters": self.board.counters()})
        self._subscribers.add(q)
        try:
            yield reset
            yield frame("control", self.status())
            sent = 0
            for text in board:
                if limit is not None and sent >= limit:
                    return
                yield text
                sent += 1
            while limit is None or sent < limit:
                text = await q.get()
                if text is None:
                    return
                yield text
                sent += text.startswith("event: claim")
        finally:
            self._subscribers.discard(q)
