"""Fault switch: per-operation failure rate, failure mode and latency."""

import random
import threading
from typing import Literal

from pydantic import BaseModel, Field

SoapOperation = Literal["UpdateCustomFields", "AddNote", "TransferWorkItem"]

# fault: a SOAP Fault comes back and nothing is applied.
# silent_drop: OK comes back but nothing is applied (only a verify read catches it).
# lost_response: the change is applied but a Fault comes back (a naive retry would repeat it).
FaultMode = Literal["fault", "silent_drop", "lost_response"]


class FaultConfig(BaseModel):
    failure_rate: float = Field(default=0.0, ge=0, le=1)
    mode: FaultMode = "fault"
    latency_ms: int = Field(default=0, ge=0)
    # Stop failing after this many injected failures (None = keep failing).
    max_failures: int | None = Field(default=None, ge=0)


class FaultSwitch:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._lock = threading.Lock()
        self._rng = rng or random.Random()
        self._configs: dict[SoapOperation, FaultConfig] = {}
        self._failures: dict[SoapOperation, int] = {}

    def configs(self) -> dict[SoapOperation, FaultConfig]:
        with self._lock:
            return dict(self._configs)

    def set(self, configs: dict[SoapOperation, FaultConfig]) -> None:
        with self._lock:
            for op, config in configs.items():
                self._configs[op] = config
                self._failures[op] = 0

    def reset(self) -> None:
        with self._lock:
            self._configs.clear()
            self._failures.clear()

    def roll(self, op: SoapOperation) -> tuple[FaultMode | None, float]:
        """Decide one call's fate: (failure mode or None, latency in seconds)."""
        with self._lock:
            config = self._configs.get(op)
            if config is None:
                return None, 0.0
            latency = config.latency_ms / 1000
            used = self._failures.get(op, 0)
            if config.max_failures is not None and used >= config.max_failures:
                return None, latency
            if self._rng.random() >= config.failure_rate:
                return None, latency
            self._failures[op] = used + 1
            return config.mode, latency
