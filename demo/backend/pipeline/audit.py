"""The decision-level audit record (compliance floor) and the ClaimsPro custom-field write."""

import hashlib
import json
from typing import Any

from claimspro_sim import ClaimsProSim, WriteResult, reliable_write
from models import AuditRecord, Claim, Signals, Stage

PIPELINE_VERSION = "routing-v0.4.0"  # the monitor stamps its events with this too


def input_data_ref(claim: Claim) -> str:
    """Points at exactly what the pipeline read: the claim as received, hashed."""
    received = claim.model_dump_json(
        exclude={"skills", "tier", "routing_reason", "review_lane", "brief_status", "write_status"}
    )
    return f"claimspro:{claim.claim_id}@sha256:{hashlib.sha256(received.encode()).hexdigest()}"


def build_audit(
    claim: Claim, signals: Signals, output: dict[str, Any], rationale: str
) -> AuditRecord:
    """Five required fields plus rationale. The pipeline routes; a person decides."""
    return AuditRecord(
        claim_id=claim.claim_id,
        input_data_ref=input_data_ref(claim),
        model_version=f"{PIPELINE_VERSION}+signals:{signals.source}",
        output=output,
        confidence=signals.confidence,
        human_reviewed=False,
        rationale=rationale,
        skills=claim.skills,
        tier=claim.tier,
    )


def write_custom_fields(sim: ClaimsProSim | None, claim: Claim) -> WriteResult | None:
    """Verified, retried write of the routing fields; no-op when there is no ClaimsPro."""
    if sim is None:
        return None
    fields = {
        "skills": [s.value for s in claim.skills],
        "tier": claim.tier,
        "routing_reason": claim.routing_reason,
        "review_lane": claim.review_lane,
        "brief_status": "pending",
    }
    # Same fields, same key: a re-run replays the change instead of applying it twice.
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()
    return reliable_write(
        sim,
        "UpdateCustomFields",
        claim.claim_id,
        {"fields": fields},
        idempotency_key=f"{PIPELINE_VERSION}:{claim.claim_id}:fields:{digest[:16]}",
        stage=Stage.ASSIGNED,
        pipeline_version=PIPELINE_VERSION,
    )
