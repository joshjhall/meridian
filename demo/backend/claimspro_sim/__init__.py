"""In-memory ClaimsPro simulator (#2).

Same shape as the real interface (CLAUDE.md, Systems snapshot): REST-style reads,
SOAP-style writes, and no claim-decisioning operation. A fault switch makes writes
fail, and `reliable_write` handles that with a verify read, bounded retries and an
alert to people.
"""

from claimspro_sim.faults import FaultConfig, FaultSwitch, SoapOperation
from claimspro_sim.reliable import ALERT_RECIPIENTS, WriteResult, reliable_write
from claimspro_sim.sim import ClaimsProSim
from claimspro_sim.soap import ClaimsProSoapClient, SoapResponse
from claimspro_sim.store import ClaimsProStore

__all__ = [
    "ALERT_RECIPIENTS",
    "ClaimsProSim",
    "ClaimsProSoapClient",
    "ClaimsProStore",
    "FaultConfig",
    "FaultSwitch",
    "SoapOperation",
    "SoapResponse",
    "WriteResult",
    "reliable_write",
]
