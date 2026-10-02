"""Build the six side-panel claim fixtures in demo/data/claims/.

Extract numbers come from reference/claims_processing.csv (never retyped);
each claim's intake details and story come from the overlay below. Real
claims cite their sample_claims/ files; synthetic ones carry synthetic=true
and a story from docs/presentation/panel_examples.md.

received_at is demo time, not the real receipt: each claim arrives
sla_used_hours before the demo clock starts, so at the default clock it shows
the SLA state the spec expects. The real dates stay in filed_date and sources.

Run: uv run --project demo/backend python demo/data/build_claims.py
"""

import csv
import sys
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "demo" / "backend"))

from clock import DEMO_START  # noqa: E402
from models import ClaimFixture  # noqa: E402

EXTRACT = REPO / "reference" / "claims_processing.csv"
OUT = Path(__file__).resolve().parent / "claims"
SPEC = "docs/presentation/panel_examples.md"

OVERLAYS: dict[str, dict] = {
    "IS-CLM-2025000300": {
        "sla_used_hours": 4,
        "sources": [
            "sample_claims/IS-CLM-2025000300/intake.md",
            "sample_claims/IS-CLM-2025000300/adjuster_notes.md",
            "sample_claims/IS-CLM-2025000300/status_history.md",
            "sample_claims/IS-CLM-2025000300/repair_estimate.pdf",
        ],
        "details": {
            "policyholder": "Sunstate Logistics LLC",
            "policy_number": "CA-FL-4471-19",
            "vehicle": "2013 Acura TSX",
            "vin": "JH4CU2F63DC802291",
            "plate": "FL SLX-4471",
            "loss_description": (
                "Insured vehicle struck a stationary parking-lot bollard at low speed. "
                "Damage to front-left bumper cover, LH headlamp, and fender. "
                "No injuries. Single vehicle, no third party."
            ),
            "injuries": False,
            "third_party": False,
            "estimate": "Gulf Coast Collision Center, est. GC-24418",
            "photos": ["IMG_0071.jpg", "IMG_0072.jpg"],
            "complete_at_intake": True,
        },
        "expected": {
            "skills": ["Collision"],
            "tier": "T1",
            "regulated": False,
            "routing_reason": "Simple collision, complete at intake → T1 fast lane",
            "sla_in_demo": "on_track",
        },
    },
    "IS-CLM-2025004222": {
        "sla_used_hours": 20,
        "sources": [
            "sample_claims/IS-CLM-2025004222/intake.md",
            "sample_claims/IS-CLM-2025004222/call_excerpt.md",
            "sample_claims/IS-CLM-2025004222/adjuster_notes.md",
            "sample_claims/IS-CLM-2025004222/status_history.md",
            "sample_claims/IS-CLM-2025004222/medical_summary.pdf",
        ],
        "details": {
            "policyholder": "Empire State Carriers Inc.",
            "policy_number": "CA-NY-30712-20",
            "claimant": "Raymond Ellison",
            "date_of_loss": "2025-09-19",
            "loss_description": (
                "Insured commercial vehicle rear-ended the claimant's vehicle on I-90 "
                "in the Buffalo area. Claimant, a restrained driver, reports neck and "
                "lower-back injury."
            ),
            "police_report": "NYSP",
            # Hand transcription: the PDF is a scanned image with no text layer.
            "medical_summary": {
                "provider": "Erie County Orthopaedic & Spine Associates",
                "date_of_service": "2025-09-22",
                "date_of_loss": "2025-09-19",
                "chief_complaint": (
                    "Neck and lower-back pain following motor-vehicle collision "
                    "(rear impact, restrained driver)."
                ),
                "assessment": [
                    "Cervical strain (S13.4XXA)",
                    "Lumbar strain (S33.5XXA)",
                    "R/O disc involvement; MRI ordered",
                ],
                "plan": "NSAIDs; physical therapy 3x/wk x 6 wks; re-eval 4 wks.",
                "work_status": (
                    "Out of work pending re-evaluation. No lifting > 10 lb, "
                    "no operation of commercial vehicles until cleared."
                ),
                "charges_usd": {"visit": 485.00, "mri_estimated": 2150.00},
            },
        },
        "expected": {
            "skills": ["Bodily Injury"],
            "tier": "T3",
            "regulated": True,
            "routing_reason": "BI over $10K in NY → T3 senior first",
            "sla_in_demo": "at_risk",
        },
    },
    "IS-CLM-2025002993": {
        "sla_used_hours": 21,
        "sources": [
            "sample_claims/IS-CLM-2025002993/intake.md",
            "sample_claims/IS-CLM-2025002993/ocr_output.txt",
            "sample_claims/IS-CLM-2025002993/edi_record.txt",
            "sample_claims/IS-CLM-2025002993/adjuster_notes.md",
            "sample_claims/IS-CLM-2025002993/status_history.md",
            "sample_claims/IS-CLM-2025002993/fax_transmission.pdf",
        ],
        "details": {
            "policyholder": "Pacific Freight Partners Inc.",
            "policy_number": "CA-CA-88123-18",
            "claimant": "Gloria Mendez",
            "vehicle": "2018 Freightliner M2 106",
            "loss_description": (
                "Reported rear-end collision involving the insured commercial vehicle; "
                "claimant alleges bodily injury and vehicle damage. Received by fax from "
                "Inland Auto Body; OCR'd on receipt and loaded via EDI 837."
            ),
            "ocr_confidence": 0.69,
            "date_of_loss": None,
        },
        "expected": {
            "skills": ["Bodily Injury", "Collision"],
            "tier": "T3",
            "regulated": True,
            "routing_reason": "BI over $10K in CA, messy fax/EDI intake → T3 senior",
            "sla_in_demo": "at_risk",
        },
    },
    "IS-CLM-2025000375": {
        "synthetic": True,
        "sla_used_hours": 30,
        "sources": [SPEC],
        "details": {
            "story": (
                "A hailstorm damaged the insured's box truck while parked overnight "
                "at a depot. Shop estimate and 5 photos on file."
            ),
            "peril": "weather (hail)",
            "photos_count": 5,
            "weather_corroboration": "Hail confirmed at the depot ZIP on the date of loss",
        },
        "expected": {
            "skills": ["Comprehensive"],
            "tier": "T2",
            "regulated": True,
            "routing_reason": "Regulated (GA, over $10K): required review was missing; added",
            "sla_in_demo": "breached",
        },
    },
    "IS-CLM-2025004518": {
        "synthetic": True,
        "sla_used_hours": 9,
        "sources": [SPEC],
        "details": {
            "story": (
                "Collision at a signalled intersection; each driver says the other ran "
                "the light. The other driver's carrier has sent a third-party demand."
            ),
            "police_report": "No fault assigned",
            "witnesses": 1,
            "third_party_demand": True,
            "accounts": [
                {
                    "party": "Insured driver",
                    "says": "Other driver ran the red light",
                    "source": "call transcript",
                },
                {
                    "party": "Claimant",
                    "says": "Insured driver ran the red light",
                    "source": "claimant statement",
                },
            ],
        },
        "expected": {
            "skills": ["Liability", "Collision"],
            "tier": "T2",
            "regulated": True,
            "routing_reason": "Regulated (PA, over $10K): required review was missing; added",
            "sla_in_demo": "on_track",
        },
    },
    "IS-CLM-2025002043": {
        "synthetic": True,
        "sla_used_hours": 12,
        "sources": [SPEC],
        "details": {
            "story": (
                "The insured's delivery truck backed into a gas station's canopy column. "
                "The owner phoned it in; there is no estimate yet."
            ),
            "property_owner": "Gas station (third party), contact on file",
            "property_type": "Canopy column",
            "missing": ["repair estimate or invoice", "photos", "insured driver's statement"],
            "amount_basis": "Owner's verbal figure",
        },
        "expected": {
            "skills": ["Property Damage"],
            "tier": "T2",
            "regulated": True,
            "routing_reason": "Regulated (FL, over $10K): required review was missing; added",
            "sla_in_demo": "on_track",
        },
    },
}


def extract_rows(ids: set[str]) -> dict[str, dict]:
    with EXTRACT.open(newline="") as f:
        rows = {r["claim_id"]: r for r in csv.DictReader(f) if r["claim_id"] in ids}
    missing = ids - rows.keys()
    if missing:
        raise SystemExit(f"claims not found in extract: {sorted(missing)}")
    # Blank cells mean "not recorded"; let the model's None defaults apply.
    return {cid: {k: v for k, v in r.items() if v != ""} for cid, r in rows.items()}


def build() -> list[ClaimFixture]:
    rows = extract_rows(set(OVERLAYS))
    fixtures = []
    for claim_id, overlay in OVERLAYS.items():
        overlay = dict(overlay)
        expected = overlay.pop("expected")
        used = timedelta(hours=overlay.pop("sla_used_hours"))
        overlay["received_at"] = DEMO_START - used
        fixtures.append(
            ClaimFixture.model_validate(
                {"claim": {**rows[claim_id], **overlay}, "expected": expected}
            )
        )
    return fixtures


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for fixture in build():
        path = OUT / f"{fixture.claim.claim_id}.json"
        path.write_text(fixture.model_dump_json(indent=2, exclude={"claim": {"sla_due_at"}}) + "\n")
        print(f"wrote {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
