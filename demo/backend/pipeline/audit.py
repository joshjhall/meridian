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


def model_version(signals: Signals) -> str:
    """The pipeline, where its signals came from, and the LLM behind them if any."""
    llm = f":{signals.llm_model}" if signals.llm_model else ""
    return f"{PIPELINE_VERSION}+signals:{signals.source}{llm}"


def signals_meta(signals: Signals) -> dict[str, Any]:
    """What the complexity step contributed, for the audit record."""
    return {
        "source": signals.source,
        "llm_model": signals.llm_model,
        "latency_ms": signals.latency_ms,
        "fallback": signals.fallback,
        "fallback_reason": signals.fallback_reason,
        "base_url_host": signals.base_url_host,
        "verified": sum(i.verified for i in signals.items),
        "unverified": len(signals.unverified),
    }


def build_audit(
    claim: Claim, signals: Signals, output: dict[str, Any], rationale: str
) -> AuditRecord:
    """Five required fields plus rationale. The pipeline routes; a person decides."""
    return AuditRecord(
        claim_id=claim.claim_id,
        input_data_ref=input_data_ref(claim),
        model_version=model_version(signals),
        output=output | {"signals": signals_meta(signals)},
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
