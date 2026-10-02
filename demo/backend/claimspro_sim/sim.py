"""One simulator instance: store, fault switch, SOAP client, and the event and alert logs."""

import random
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime

from claimspro_sim.faults import FaultSwitch
from claimspro_sim.soap import ClaimsProSoapClient
from claimspro_sim.store import ClaimsProStore
from models import Alert, Claim, PipelineEvent


class ClaimsProSim:
    """Tests inject `sleep`, `now` and `rng` to run instantly and give the same result each time."""

    def __init__(
        self,
        claims: Iterable[Claim] | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = datetime.now,
        rng: random.Random | None = None,
    ) -> None:
        self.sleep = sleep
        self.now = now
        self.store = ClaimsProStore(claims)
        self.faults = FaultSwitch(rng)
        self.soap = ClaimsProSoapClient(self.store, self.faults, sleep, now)
        self._lock = threading.Lock()
        self._events: list[PipelineEvent] = []
        self._alerts: list[Alert] = []

    def record_event(self, event: PipelineEvent) -> None:
        with self._lock:
            self._events.append(event)

    def record_alert(self, alert: Alert) -> None:
        with self._lock:
            self._alerts.append(alert)

    def events(self, claim_id: str | None = None) -> list[PipelineEvent]:
        with self._lock:
            return [e for e in self._events if claim_id is None or e.claim_id == claim_id]

    def alerts(self) -> list[Alert]:
        with self._lock:
            return list(self._alerts)
