"""REST-style reads and the fault switch, mounted by app.py.

Reads live under /api so they don't collide with the /claimspro/{claim_id} page (#10).
There are no write endpoints here: writes go through `reliable_write`.
"""

from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from claimspro_sim.faults import FaultConfig, SoapOperation
from claimspro_sim.sim import ClaimsProSim
from models import Alert, Claim, ClaimNote, PipelineEvent

router = APIRouter(prefix="/api")


@cache
def get_sim() -> ClaimsProSim:
    return ClaimsProSim()


Sim = Annotated[ClaimsProSim, Depends(get_sim)]
FaultConfigs = dict[SoapOperation, FaultConfig]


def _claim_or_404(sim: ClaimsProSim, claim_id: str) -> Claim:
    claim = sim.store.get(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"unknown claim {claim_id}")
    return claim


@router.get("/claimspro/claims")
def list_claims(sim: Sim, assignee: str | None = None) -> list[Claim]:
    return sim.store.list_claims(assignee)


@router.get("/claimspro/claims/{claim_id}")
def get_claim(sim: Sim, claim_id: str) -> Claim:
    return _claim_or_404(sim, claim_id)


@router.get("/claimspro/claims/{claim_id}/notes")
def get_notes(sim: Sim, claim_id: str) -> list[ClaimNote]:
    _claim_or_404(sim, claim_id)
    return sim.store.notes(claim_id)


@router.get("/sim/faults")
def get_faults(sim: Sim) -> FaultConfigs:
    return sim.faults.configs()


@router.post("/sim/faults")
def set_faults(sim: Sim, configs: FaultConfigs) -> FaultConfigs:
    sim.faults.set(configs)
    return sim.faults.configs()


@router.delete("/sim/faults")
def reset_faults(sim: Sim) -> FaultConfigs:
    sim.faults.reset()
    return sim.faults.configs()


@router.get("/sim/events")
def list_events(sim: Sim, claim_id: str | None = None) -> list[PipelineEvent]:
    return sim.events(claim_id)


@router.get("/sim/alerts")
def list_alerts(sim: Sim) -> list[Alert]:
    return sim.alerts()
