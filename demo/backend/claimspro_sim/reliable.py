"""Reliable writes: write → wait → verify read → retry with backoff → escalate to people.

ClaimsPro SOAP writes can fault, or return OK without persisting. Every attempt of
one intended change reuses the same idempotency key, so a retry after a write that
did land (but whose response was lost) never applies the change twice.
"""

import uuid
from typing import Any, Literal

from pydantic import BaseModel

from claimspro_sim.faults import SoapOperation
from claimspro_sim.sim import ClaimsProSim
from models import Alert, PipelineEvent, Stage, WriteStatus

ALERT_RECIPIENTS = ["tribe-engineering", "client-it"]
SIM_VERSION = "claimspro-sim-0.1"


class WriteResult(BaseModel):
    status: Literal["confirmed", "write_failed"]
    attempts: int
    idempotency_key: str
    alert: Alert | None = None


def reliable_write(
    sim: ClaimsProSim,
    op: SoapOperation,
    claim_id: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
    verify_delay_s: float = 0.2,
    base_backoff_s: float = 0.5,
    stage: Stage = Stage.ASSIGNED,
    pipeline_version: str = SIM_VERSION,
) -> WriteResult:
    """Apply one intended change. Pass the same key to replay a change already sent."""
    sim.soap.check(op, claim_id, payload)  # rejected requests are never retried
    key = idempotency_key or str(uuid.uuid4())

    def emit(status: WriteStatus, attempt: int, reason: str | None = None) -> None:
        sim.record_event(
            PipelineEvent(
                claim_id=claim_id,
                stage=stage,
                timestamp=sim.now(),
                pipeline_version=pipeline_version,
                payload={
                    "operation": op,
                    "write_status": status,
                    "attempt": attempt,
                    "idempotency_key": key,
                    "reason": reason,
                },
            )
        )

    sim.store.set_write_status(claim_id, "pending")
    emit("pending", 1)
    reason = ""
    for attempt in range(1, max_attempts + 1):
        response = sim.soap.call(op, claim_id, payload, key)
        # Verify even after a fault: the write may have landed and only the response was lost.
        sim.sleep(verify_delay_s)
        if sim.soap.is_applied(op, claim_id, payload, key):
            sim.store.set_write_status(claim_id, "confirmed")
            emit("confirmed", attempt)
            return WriteResult(status="confirmed", attempts=attempt, idempotency_key=key)
        if response.ok:
            reason = "write returned OK but the verify read does not show it"
        else:
            reason = response.fault or "SOAP fault"
        if attempt < max_attempts:
            emit("retrying", attempt, reason)
            sim.sleep(base_backoff_s * 2 ** (attempt - 1))

    sim.store.set_write_status(claim_id, "write_failed")
    emit("failed", max_attempts, reason)
    alert = Alert(
        claim_id=claim_id,
        operation=op,
        idempotency_key=key,
        recipients=ALERT_RECIPIENTS,
        message=f"{op} on {claim_id} failed after {max_attempts} attempts: {reason}",
        raised_at=sim.now(),
    )
    sim.record_alert(alert)
    return WriteResult(
        status="write_failed", attempts=max_attempts, idempotency_key=key, alert=alert
    )
