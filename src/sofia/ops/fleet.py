from __future__ import annotations
from dataclasses import replace
from .model import FleetHost, HostLifecycle
from .approval import FleetRemovalApproval

class FleetRemovalApprovalRequired(PermissionError): pass

_ALLOWED={
 HostLifecycle.CANDIDATE:{HostLifecycle.ENROLLED,HostLifecycle.QUARANTINED},
 HostLifecycle.ENROLLED:{HostLifecycle.HEALTHY,HostLifecycle.DEGRADED,HostLifecycle.QUARANTINED,HostLifecycle.OFFLINE},
 HostLifecycle.HEALTHY:{HostLifecycle.DEGRADED,HostLifecycle.MAINTENANCE,HostLifecycle.DRAINING,HostLifecycle.QUARANTINED,HostLifecycle.OFFLINE},
 HostLifecycle.DEGRADED:{HostLifecycle.HEALTHY,HostLifecycle.MAINTENANCE,HostLifecycle.DRAINING,HostLifecycle.QUARANTINED,HostLifecycle.OFFLINE},
 HostLifecycle.MAINTENANCE:{HostLifecycle.HEALTHY,HostLifecycle.DEGRADED,HostLifecycle.DRAINING,HostLifecycle.QUARANTINED},
 HostLifecycle.DRAINING:{HostLifecycle.MAINTENANCE,HostLifecycle.QUARANTINED,HostLifecycle.DECOMMISSIONED},
 HostLifecycle.QUARANTINED:{HostLifecycle.DRAINING,HostLifecycle.ENROLLED,HostLifecycle.DECOMMISSIONED},
 HostLifecycle.OFFLINE:{HostLifecycle.ENROLLED,HostLifecycle.QUARANTINED,HostLifecycle.DRAINING},
 HostLifecycle.DECOMMISSIONED:set(),
}

class FleetRegistry:
    def __init__(self)->None: self._hosts:dict[str,FleetHost]={}
    def register_candidate(self,host:FleetHost)->None:
        if host.lifecycle is not HostLifecycle.CANDIDATE: raise ValueError("new host must begin as candidate")
        if host.host_id in self._hosts and self._hosts[host.host_id]!=host: raise ValueError("host identity conflict")
        self._hosts[host.host_id]=host
    def host(self,host_id:str)->FleetHost|None: return self._hosts.get(host_id)
    def hosts(self)->tuple[FleetHost,...]: return tuple(self._hosts[k] for k in sorted(self._hosts))
    def transition(self,host_id:str,state:HostLifecycle,*,sparks_approved_removal:bool=False)->FleetHost:
        host=self._hosts[host_id]
        if state not in _ALLOWED[host.lifecycle]: raise ValueError(f"invalid fleet transition: {host.lifecycle.value} -> {state.value}")
        if state is HostLifecycle.DECOMMISSIONED and not sparks_approved_removal:
            raise FleetRemovalApprovalRequired("final fleet removal requires Sparks explicit approval")
        if state is HostLifecycle.ENROLLED and not host.trusted: raise PermissionError("untrusted candidate cannot enroll")
        updated=replace(host,lifecycle=state); self._hosts[host_id]=updated; return updated
    def update_telemetry(self,host_id:str,telemetry)->FleetHost:
        host=self._hosts[host_id]; updated=replace(host,telemetry=telemetry); self._hosts[host_id]=updated; return updated

    def decommission(self,host_id:str,*,proposal_revision:str,approval:FleetRemovalApproval)->FleetHost:
        if not isinstance(approval,FleetRemovalApproval): raise TypeError("FleetRemovalApproval required")
        if approval.host_id!=host_id: raise FleetRemovalApprovalRequired("approval is for a different machine")
        if approval.proposal_revision!=proposal_revision: raise FleetRemovalApprovalRequired("approval revision does not match removal proposal")
        return self.transition(host_id,HostLifecycle.DECOMMISSIONED,sparks_approved_removal=True)
