"""Pre-processing and routing pipeline (#3): data quality and routing, with an audit record.

`run_pipeline` takes claims (or raw extract rows), the roster and the demo clock's now,
and returns every claim either routed to an adjuster in a lane or stopped for a person.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from claimspro_sim import ClaimsProSim
from models import Adjuster, Claim, PipelineEvent
from pipeline.audit import PIPELINE_VERSION
from pipeline.graph import Routed, build_pipeline


class PipelineResult(BaseModel):
    routed: list[Routed]
    events: list[PipelineEvent]

    def by_id(self) -> dict[str, Routed]:
        return {r.claim_id: r for r in self.routed}


def run_pipeline(
    claims: Iterable[Claim | dict[str, Any]],
    roster: Iterable[Adjuster],
    *,
    now: datetime,
    sim: ClaimsProSim | None = None,
) -> PipelineResult:
    """Pass clock.now() for `now`. With a sim, routing fields are written to ClaimsPro."""
    out = build_pipeline(roster, sim).invoke({"inputs": list(claims), "now": now, "events": []})
    return PipelineResult(routed=out["results"], events=out["events"])


__all__ = ["PIPELINE_VERSION", "PipelineResult", "Routed", "run_pipeline"]
