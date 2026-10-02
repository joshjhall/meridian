"""The demo clock: the one source of "now" for every SLA calculation.

Fixture claims are dated relative to DEMO_START (see demo/data/build_claims.py),
so at the default clock each shows the SLA state the spec expects. SLA code
reads time from now() here, never from the wall clock; the replay runner (#5)
moves it forward with advance().
"""

from datetime import datetime, timedelta

DEMO_START = datetime(2025, 10, 15, 9, 0)

_now = DEMO_START


def now() -> datetime:
    return _now


def advance(delta: timedelta) -> datetime:
    global _now
    _now += delta
    return _now


def reset(at: datetime = DEMO_START) -> None:
    global _now
    _now = at
