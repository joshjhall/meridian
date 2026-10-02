"""View data for the mock ClaimsPro claim page (#10).

The page stands in for Meridian's vendor system, so it shows what ClaimsPro would:
eight dense screens, the documents on file, and the pipeline's custom fields. The
anchors defined here (`#loss`, `#documents/medical-summary`) are what the side
panel's Contents section (#11) links to.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from fixtures import load_claim_fixtures
from models import TIER_LABELS, Claim

# Stand-ins for the "eight screens deep" adjusters click through (slides_draft.md).
SCREENS: list[tuple[str, str]] = [
    ("summary", "Summary"),
    ("policy", "Policy"),
    ("parties", "Parties"),
    ("loss", "Loss"),
    ("documents", "Documents"),
    ("notes", "Notes"),
    ("payments", "Payments"),
    ("history", "History"),
]

# Which screen each fixture `details` key appears on; unlisted keys go to Loss.
DETAIL_SCREENS: dict[str, str] = {
    "policyholder": "policy",
    "policy_number": "policy",
    "vehicle": "policy",
    "vin": "policy",
    "plate": "policy",
    "claimant": "parties",
    "property_owner": "parties",
    "third_party": "parties",
    "witnesses": "parties",
    "accounts": "parties",
    "third_party_demand": "parties",
    "estimate": "payments",
    "amount_basis": "payments",
    "medical_summary": "documents",
}

# Synthetic claims have no files in sample_claims/; these name the documents their
# spec story says are on file (docs/presentation/panel_examples.md).
SYNTHETIC_DOCUMENTS: dict[str, list[tuple[str, str]]] = {
    "IS-CLM-2025000375": [
        ("repair-estimate", "Shop repair estimate"),
        ("photos", "Photos (5)"),
    ],
    "IS-CLM-2025004518": [
        ("police-report", "Police report (no fault assigned)"),
        ("witness-statement", "Independent witness statement"),
        ("call-transcript", "Insured driver call transcript"),
        ("claimant-statement", "Claimant statement"),
        ("third-party-demand", "Third-party demand (other carrier)"),
    ],
    "IS-CLM-2025002043": [
        ("intake-call", "Owner's phone report"),
    ],
}

NOT_SAVED = "not yet saved"
EMPTY = "—"
SLA_LABELS = {"on_track": "on track", "at_risk": "AT RISK", "breached": "BREACHED"}
WRITE_LABELS = {"confirmed": "Saved", "pending": "Not yet saved", "write_failed": "SAVE FAILED"}


@dataclass(frozen=True)
class Document:
    slug: str
    name: str
    kind: str

    @property
    def anchor(self) -> str:
        return f"documents/{self.slug}"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", PurePosixPath(name).stem.lower()).strip("-")


def documents(claim: Claim) -> list[Document]:
    if claim.claim_id in SYNTHETIC_DOCUMENTS:
        return [Document(s, n, "synthetic") for s, n in SYNTHETIC_DOCUMENTS[claim.claim_id]]
    files = [p for p in claim.sources if p.startswith("sample_claims/")]
    files += claim.details.get("photos", [])
    return [
        Document(slugify(f), PurePosixPath(f).name, PurePosixPath(f).suffix.lstrip(".").upper())
        for f in files
    ]


def neighbours(claim_id: str) -> tuple[str, str]:
    """Previous and next of the six demo claims, wrapping at either end.

    The simulator also holds the extract's open claims, which are not among the six;
    from one of those, prev/next lead to the last and first demo claims.
    """
    ids = list(load_claim_fixtures())
    if claim_id not in ids:
        return ids[-1], ids[0]
    i = ids.index(claim_id)
    return ids[i - 1], ids[(i + 1) % len(ids)]


def custom_field_rows(claim: Claim, now: datetime) -> list[tuple[str, str]]:
    """The pipeline's ClaimsPro custom fields as label/value rows.

    While a write is in flight the stored values are the old ones, so each written
    field reads "not yet saved" rather than showing something about to change. SLA
    due is derived from receipt time, not written, so it always shows.
    """
    written: list[tuple[str, Any]] = [
        ("Skills", ", ".join(claim.skills)),
        ("Tier", claim.tier and f"{claim.tier} {TIER_LABELS[claim.tier]}"),
        ("Review lane", claim.review_lane and claim.review_lane.replace("_", " ")),
        ("Routing reason", claim.routing_reason),
        ("Brief status", claim.brief_status),
    ]
    pending = claim.write_status == "pending"
    rows = [(label, NOT_SAVED if pending else (value or EMPTY)) for label, value in written]
    sla = f"{claim.sla_due_at:%m/%d/%Y %H:%M} ({SLA_LABELS[claim.sla_state(now)]})"
    rows.insert(4, ("SLA due", sla))
    rows.append(("Last save", WRITE_LABELS.get(claim.write_status or "", EMPTY)))
    return rows


def details_by_screen(claim: Claim) -> dict[str, dict[str, Any]]:
    screens: dict[str, dict[str, Any]] = {anchor: {} for anchor, _ in SCREENS}
    for key, value in claim.details.items():
        if key == "photos":
            continue  # listed as documents
        screens[DETAIL_SCREENS.get(key, "loss")][key] = value
    return screens
