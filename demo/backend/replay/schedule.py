"""The replay sequence (#5): the extract, in filed order, through the real pipeline.

Everything here is a pure function of the seed, so a rehearsal and the live demo see
the same claims in the same order with the same outcomes. The runner only decides how
fast to play it.

Each claim runs through `run_pipeline` when it arrives, writing to one ClaimsPro
simulator per pass, so the pass's write log and alerts accumulate there. The
pipeline's exceptions come from the real code path. A seeded share of claims
meet a ClaimsPro outage, so the verified write fails after retries. A seeded
share of Fax/EDI rows arrive with a field dropped, as the EDI parser drops them
today, and fail validation.
"""

import heapq
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from claimspro_sim import ClaimsProSim, FaultConfig
from clock import DEMO_START
from fixtures import claim_from_row, extract_rows, load_claim_fixtures, load_roster
from models import Adjuster, Claim, PipelineEvent
from pipeline import PipelineResult, run_pipeline

SEED = 5
# Display pacing between one claim's events, so a card visibly moves lane to lane.
# The pipeline itself takes milliseconds; this is not a latency figure.
STEP = timedelta(minutes=15)
# Simulated hours at which the six demo claims arrive: all on screen inside the
# first minute at the default 1 simulated hour per second.
FIXTURE_AT_H = (1, 7, 14, 22, 31, 41)
OUTAGE_RATE = 0.03  # claims whose routing write meets a ClaimsPro outage
EDI_DROP_RATE = 0.05  # Fax/EDI rows arriving with a required field dropped
DROPPABLE = ("state", "claim_amount_usd", "claim_type")


@dataclass(frozen=True)
class Scheduled:
    at: datetime  # simulated time on the demo clock
    event: PipelineEvent


@dataclass(frozen=True)
class Arrival:
    at: datetime
    claim: Claim | dict[str, Any]  # a raw row when intake dropped a field
    outage: bool = False

    @property
    def claim_id(self) -> str:
        return self.claim.claim_id if isinstance(self.claim, Claim) else str(self.claim["claim_id"])

    @property
    def dropped(self) -> bool:
        return not isinstance(self.claim, Claim)


def arrivals(seed: int = SEED) -> Iterator[Arrival]:
    """Claims in arrival order: extract rows by filed date, the six fixtures at set points.

    Extract dates are moved onto the demo clock (the first filed day is DEMO_START's
    day) with a seeded time of day, and `received_at` follows, so SLA states read
    true against clock.now(). The fixtures' own extract rows are skipped.
    """
    rng = random.Random(seed)
    fixtures = load_claim_fixtures()
    rows = [r for r in extract_rows() if r["claim_id"] not in fixtures]
    first = min(date.fromisoformat(str(r["filed_date"])) for r in rows)
    timed = []
    for r in rows:
        days = (date.fromisoformat(str(r["filed_date"])) - first).days
        at = DEMO_START + timedelta(days=days, minutes=rng.randrange(24 * 60))
        # Draw both for every row, so changing one rate doesn't reshuffle the other.
        drop, outage = rng.random(), rng.random()
        dropped = rng.choice(DROPPABLE)
        if r["intake_channel"] == "Fax/EDI" and drop < EDI_DROP_RATE:
            timed.append((at, {**r, dropped: None}, False))
        else:
            timed.append((at, r, outage < OUTAGE_RATE))
    timed.sort(key=lambda t: t[0])  # stable: same-minute rows keep file order

    pinned = []
    for hours, fx in zip(FIXTURE_AT_H, fixtures.values(), strict=True):
        at = DEMO_START + timedelta(hours=hours)
        # Keep each fixture's SLA story: shift its receipt by as much as its arrival.
        claim = fx.claim.model_copy(
            update={"received_at": fx.claim.received_at + (at - DEMO_START)}
        )
        pinned.append(Arrival(at, claim))

    def extract() -> Iterator[Arrival]:
        for at, row, outage in timed:
            if any(row[f] is None for f in DROPPABLE):
                yield Arrival(at, row)
                continue
            claim = claim_from_row(row).model_copy(
                update={"filed_date": at.date(), "received_at": at}
            )
            yield Arrival(at, claim, outage)

    yield from heapq.merge(pinned, extract(), key=lambda a: a.at)


class PassSim(ClaimsProSim):
    """One pass's ClaimsPro: claims are added as they arrive, at their own simulated time.

    Faults are switched per claim, never rolled: a seeded outage claim always fails
    and no other write touches the fault RNG, so sharing it keeps the run seeded.
    """

    def __init__(self) -> None:
        self.at = DEMO_START
        # Each claim's pipeline run, with events at their replay times, for the audit record (#9).
        self.runs: dict[str, PipelineResult] = {}
        super().__init__([], sleep=lambda _: None, now=lambda: self.at)


def _run(
    arrival: Arrival, roster: list[Adjuster], loads: dict[str, int], sim: PassSim
) -> list[PipelineEvent]:
    sim.at = arrival.at
    if isinstance(arrival.claim, Claim):
        sim.store.add(arrival.claim)
    if arrival.outage:
        sim.faults.set({"UpdateCustomFields": FaultConfig(failure_rate=1.0)})
    current = [a.model_copy(update={"current_load": loads[a.id]}) for a in roster]
    try:
        result = run_pipeline([arrival.claim], current, now=arrival.at, sim=sim)
    finally:
        sim.faults.reset()
    for r in result.routed:
        if r.adjuster_id:
            loads[r.adjuster_id] += 1  # work spreads across the replay, not just one claim
    timed = [
        e.model_copy(update={"timestamp": arrival.at + i * STEP})
        for i, e in enumerate(result.events)
    ]
    sim.runs[arrival.claim_id] = result.model_copy(update={"events": timed})
    return timed


def events(seed: int = SEED, sim: PassSim | None = None) -> Iterator[Scheduled]:
    """Every pipeline event of the replay, in simulated-time order. Lazy: one claim at a time.

    Pass `sim` to keep the pass's ClaimsPro (writes, alerts) readable while it plays.
    """
    sim = sim or PassSim()
    roster = load_roster()
    loads = {a.id: a.current_load for a in roster}
    heap: list[tuple[datetime, int, Scheduled]] = []
    n = 0
    for arrival in arrivals(seed):
        while heap and heap[0][0] <= arrival.at:
            yield heapq.heappop(heap)[2]
        for event in _run(arrival, roster, loads, sim):
            heapq.heappush(heap, (event.timestamp, n, Scheduled(event.timestamp, event)))
            n += 1
    while heap:
        yield heapq.heappop(heap)[2]
