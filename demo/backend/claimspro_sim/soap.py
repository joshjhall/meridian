"""SOAP-style write operations, named after the real ClaimsPro operations.

There is deliberately no approve, deny or disposition operation: claim decisions
enter ClaimsPro through its UI or batch file only, and AI never denies a claim
(CLAUDE.md, Systems snapshot and compliance floor). UpdateCustomFields can write
only the pipeline's custom fields, so it can't be used to set a disposition either.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from claimspro_sim.faults import FaultSwitch, SoapOperation
from claimspro_sim.store import ClaimsProStore
from fixtures import load_roster
from models import Claim, ClaimNote

CUSTOM_FIELDS = frozenset({"skills", "tier", "routing_reason", "review_lane", "brief_status"})


class SoapResponse(BaseModel):
    ok: bool
    fault: str | None = None


class SoapClientError(ValueError):
    """A request ClaimsPro rejects outright (unknown claim, field or adjuster); never retried."""


class ClaimsProSoapClient:
    def __init__(
        self,
        store: ClaimsProStore,
        faults: FaultSwitch,
        sleep: Callable[[float], None],
        now: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._faults = faults
        self._sleep = sleep
        self._now = now

    # --- Operations ---

    def UpdateCustomFields(  # CapitalCase: named after the SOAP operations
        self, claim_id: str, fields: dict[str, Any], idempotency_key: str
    ) -> SoapResponse:
        values = self._custom_field_values(claim_id, fields)

        def change(claim: Claim) -> None:
            for name, value in values.items():
                setattr(claim, name, value)

        return self._call(
            "UpdateCustomFields", lambda: self._store.apply(idempotency_key, change, claim_id)
        )

    def AddNote(self, claim_id: str, text: str, author: str, idempotency_key: str) -> SoapResponse:
        self._require_claim(claim_id)
        note = ClaimNote(text=text, author=author, idempotency_key=idempotency_key, at=self._now())
        return self._call("AddNote", lambda: self._store.add_note(idempotency_key, note, claim_id))

    def TransferWorkItem(
        self, claim_id: str, to_adjuster_id: str, idempotency_key: str
    ) -> SoapResponse:
        self._require_claim(claim_id)
        self._require_adjuster(to_adjuster_id)

        def change(claim: Claim) -> None:
            claim.adjuster_id = to_adjuster_id

        return self._call(
            "TransferWorkItem", lambda: self._store.apply(idempotency_key, change, claim_id)
        )

    # --- Dispatch by operation name, request checks, and the verify read for each ---

    def check(self, op: SoapOperation, claim_id: str, payload: dict[str, Any]) -> None:
        """Raise SoapClientError for a request ClaimsPro would reject, before anything is sent."""
        match op:
            case "UpdateCustomFields":
                self._custom_field_values(claim_id, payload["fields"])
            case "TransferWorkItem":
                self._require_claim(claim_id)
                self._require_adjuster(payload["to_adjuster_id"])
            case "AddNote":
                self._require_claim(claim_id)

    def call(
        self, op: SoapOperation, claim_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> SoapResponse:
        return getattr(self, op)(claim_id, **payload, idempotency_key=idempotency_key)

    def is_applied(
        self, op: SoapOperation, claim_id: str, payload: dict[str, Any], idempotency_key: str
    ) -> bool:
        """REST-style read: does ClaimsPro now show the intended change?"""
        claim = self._store.get(claim_id)
        if claim is None:
            return False
        match op:
            case "UpdateCustomFields":
                wanted = self._custom_field_values(claim_id, payload["fields"])
                return all(getattr(claim, k) == v for k, v in wanted.items())
            case "TransferWorkItem":
                return claim.adjuster_id == payload["to_adjuster_id"]
            case "AddNote":
                notes = self._store.notes(claim_id)
                return any(n.idempotency_key == idempotency_key for n in notes)

    # --- Internals ---

    def _call(self, op: SoapOperation, apply: Callable[[], bool]) -> SoapResponse:
        mode, latency = self._faults.roll(op)
        if latency:
            self._sleep(latency)
        match mode:
            case "fault":
                return SoapResponse(ok=False, fault=f"{op}: service unavailable")
            case "silent_drop":
                return SoapResponse(ok=True)
            case "lost_response":
                apply()
                return SoapResponse(ok=False, fault=f"{op}: response timed out")
            case None:
                apply()
                return SoapResponse(ok=True)

    def _require_claim(self, claim_id: str) -> Claim:
        claim = self._store.get(claim_id)
        if claim is None:
            raise SoapClientError(f"unknown claim {claim_id}")
        return claim

    def _require_adjuster(self, adjuster_id: str) -> None:
        if adjuster_id not in {a.id for a in load_roster()}:
            raise SoapClientError(f"unknown adjuster {adjuster_id}")

    def _custom_field_values(self, claim_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Validate the fields against the Claim model and return the parsed values."""
        not_custom = set(fields) - CUSTOM_FIELDS
        if not_custom:
            raise SoapClientError(f"not writable custom fields: {sorted(not_custom)}")
        claim = self._require_claim(claim_id)
        try:
            updated = Claim.model_validate({**claim.model_dump(), **fields})
        except ValidationError as e:
            raise SoapClientError(f"invalid custom field value: {e}") from e
        return {name: getattr(updated, name) for name in fields}
