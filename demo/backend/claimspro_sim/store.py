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
        self._applied_keys: set[str] = set()

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
            return [n.model_copy() for n in self._notes[claim_id]]

    # --- Writes (only the SOAP operations and the reliable-write wrapper call these) ---

    def apply(self, idempotency_key: str, change: Callable[[Claim], None], claim_id: str) -> bool:
        """Apply `change` once per key. Returns False when the key was already applied."""
        with self._lock:
            if idempotency_key in self._applied_keys:
                return False
            change(self._claims[claim_id])
            self._applied_keys.add(idempotency_key)
            return True

    def add_note(self, idempotency_key: str, note: ClaimNote, claim_id: str) -> bool:
        with self._lock:
            if idempotency_key in self._applied_keys:
                return False
            self._notes[claim_id].append(note)
            self._applied_keys.add(idempotency_key)
            return True

    def set_write_status(self, claim_id: str, status: ClaimWriteStatus) -> None:
        # Demo shortcut: in production this status lives on our side, not in ClaimsPro.
        with self._lock:
            self._claims[claim_id].write_status = status
