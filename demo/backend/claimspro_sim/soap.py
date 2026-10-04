"""SOAP-style write operations, named after the real ClaimsPro operations.

There is deliberately no approve, deny or disposition operation: claim decisions
enter ClaimsPro through its UI or batch file only, and AI never denies a claim
(CLAUDE.md, Systems snapshot and compliance floor). UpdateCustomFields can write
only the pipeline's custom fields, so it can't be used to set a disposition either.
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from claimspro_sim.faults import FaultSwitch, SoapOperation
from claimspro_sim.store import ClaimsProStore
from fixtures import load_roster
from models import Claim, ClaimNote

PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    "UpdateCustomFields": frozenset({"fields"}),
    "TransferWorkItem": frozenset({"to_adjuster_id"}),
    "AddNote": frozenset({"text", "author"}),
}
CUSTOM_FIELDS = frozenset(
    {"skills", "tier", "routing_reason", "review_lane", "brief_status", "intake_status"}
)


def intent(op: SoapOperation, claim_id: str, payload: dict[str, Any]) -> str:
    """Canonical description of one change, bound to its idempotency key."""
    return json.dumps([op, claim_id, payload], sort_keys=True, default=str)


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
            "UpdateCustomFields",
            lambda: self._store.update_claim(
                idempotency_key,
                intent("UpdateCustomFields", claim_id, {"fields": fields}),
                claim_id,
                change,
            ),
        )

    def AddNote(self, claim_id: str, text: str, author: str, idempotency_key: str) -> SoapResponse:
        self._require_claim(claim_id)
        note = ClaimNote(text=text, author=author, idempotency_key=idempotency_key, at=self._now())
        key_intent = intent("AddNote", claim_id, {"text": text, "author": author})
        return self._call(
            "AddNote", lambda: self._store.add_note(idempotency_key, key_intent, claim_id, note)
        )

    def TransferWorkItem(
        self, claim_id: str, to_adjuster_id: str, idempotency_key: str
    ) -> SoapResponse:
        self._require_claim(claim_id)
        self._require_adjuster(to_adjuster_id)

        def change(claim: Claim) -> None:
            claim.adjuster_id = to_adjuster_id

        return self._call(
            "TransferWorkItem",
            lambda: self._store.update_claim(
                idempotency_key,
                intent("TransferWorkItem", claim_id, {"to_adjuster_id": to_adjuster_id}),
                claim_id,
                change,
            ),
        )

    # --- Dispatch by operation name, request checks, and the verify read for each ---

    def check(self, op: SoapOperation, claim_id: str, payload: dict[str, Any]) -> None:
        """Raise SoapClientError for a request ClaimsPro would reject, before anything is sent."""
        if set(payload) != PAYLOAD_KEYS[op]:
            raise SoapClientError(f"{op} takes {sorted(PAYLOAD_KEYS[op])}, got {sorted(payload)}")
        if op == "UpdateCustomFields" and not isinstance(payload["fields"], dict):
            raise SoapClientError("UpdateCustomFields fields must be a mapping")
        if any(not isinstance(v, str) for k, v in payload.items() if k != "fields"):
            raise SoapClientError(f"{op} values must be strings")
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
        """REST-style read: does ClaimsPro now show the intended change?

        A key ClaimsPro has recorded as applied is proof on its own, so replaying a change
        after later writes still confirms. Otherwise notes are matched by key and field and
        transfer writes by state, so a change the claim already reflects counts as confirmed.
        """
        if self._store.key_applied(idempotency_key, intent(op, claim_id, payload)):
            return True
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
