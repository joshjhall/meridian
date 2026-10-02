"""The simulator's system of record: claims, notes and applied idempotency keys."""

import csv
import threading
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime

from fixtures import DATA, load_claim_fixtures
from models import Claim, ClaimNote, ClaimWriteStatus

EXTRACT = DATA.parents[1] / "reference" / "claims_processing.csv"


def seed_claims() -> list[Claim]:
    """The six fixtures plus the extract's open work ("Pending Review"); fixtures win on ID."""
    claims = {c.claim_id: c for c in _open_extract_claims()}
    claims.update((cid, f.claim) for cid, f in load_claim_fixtures().items())
    return list(claims.values())


def _open_extract_claims() -> Iterable[Claim]:
    with EXTRACT.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["disposition"] != "Pending Review":
                continue
            fields = {k: v or None for k, v in row.items()}
            yield Claim.model_validate(
                {**fields, "received_at": datetime.fromisoformat(row["filed_date"])}
            )


class ClaimsProStore:
    """Claims are deep copies, so writes never touch the cached fixtures."""

    def __init__(self, claims: Iterable[Claim] | None = None) -> None:
        self._lock = threading.Lock()
        source = seed_claims() if claims is None else claims
        self._claims = {c.claim_id: c.model_copy(deep=True) for c in source}
        self._notes: defaultdict[str, list[ClaimNote]] = defaultdict(list)
        self._applied_keys: dict[str, tuple[str, str]] = {}

    # --- Reads (what the REST endpoints return; snapshots, never live objects) ---

    def get(self, claim_id: str) -> Claim | None:
        with self._lock:
            claim = self._claims.get(claim_id)
            return None if claim is None else claim.model_copy(deep=True)

    def list_claims(self, assignee: str | None = None) -> list[Claim]:
        with self._lock:
            return [
                c.model_copy(deep=True)
                for c in self._claims.values()
                if assignee is None or c.adjuster_id == assignee
            ]

    def notes(self, claim_id: str) -> list[ClaimNote]:
        with self._lock:
            return [n.model_copy() for n in self._notes.get(claim_id, [])]

    # --- Writes (only the SOAP operations and the reliable-write wrapper call these) ---

    def apply(
        self, idempotency_key: str, operation: str, claim_id: str, change: Callable[[], None]
    ) -> bool:
        """Run `change` once per key. Returns False when the key was already applied.

        A key reused for a different claim or operation is a caller bug, so it raises
        rather than silently dropping the second change.
        """
        scope = (claim_id, operation)
        with self._lock:
            seen = self._applied_keys.get(idempotency_key)
            if seen == scope:
                return False
            if seen is not None:
                raise ValueError(f"idempotency key {idempotency_key} already used for {seen}")
            change()
            self._applied_keys[idempotency_key] = scope
            return True

    def update_claim(
        self, idempotency_key: str, operation: str, claim_id: str, change: Callable[[Claim], None]
    ) -> bool:
        return self.apply(
            idempotency_key, operation, claim_id, lambda: change(self._claims[claim_id])
        )

    def add_note(self, idempotency_key: str, claim_id: str, note: ClaimNote) -> bool:
        return self.apply(
            idempotency_key, "AddNote", claim_id, lambda: self._notes[claim_id].append(note)
        )

    def set_write_status(self, claim_id: str, status: ClaimWriteStatus) -> None:
        # Demo shortcut: in production this status lives on our side, not in ClaimsPro.
        with self._lock:
            self._claims[claim_id].write_status = status
