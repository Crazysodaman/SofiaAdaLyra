"""Fail-closed promotion checks for standby workload authority."""
from __future__ import annotations
from dataclasses import dataclass
from .fleet import FleetRegistry
from .model import HostLifecycle

class PromotionDenied(PermissionError): pass

@dataclass(frozen=True)
class FailureDomain:
    host_id:str; domain_id:str
    def __post_init__(self):
        if not self.host_id.strip() or not self.domain_id.strip(): raise ValueError("failure-domain identity required")

@dataclass(frozen=True)
class PromotionEvidence:
    workload_id:str; source_host_id:str; target_host_id:str
    state_verified:bool; source_fenced:bool; witness_quorum:bool

class PromotionGuard:
    def __init__(self,registry:FleetRegistry,domains:tuple[FailureDomain,...])->None:
        self.registry=registry; self.domains={d.host_id:d.domain_id for d in domains}
    def require(self,evidence:PromotionEvidence)->None:
        target=self.registry.host(evidence.target_host_id)
        if target is None or not target.trusted or target.lifecycle is not HostLifecycle.HEALTHY:
            raise PromotionDenied("target must be a trusted healthy enrolled host")
        source_domain=self.domains.get(evidence.source_host_id); target_domain=self.domains.get(evidence.target_host_id)
        if source_domain is None or target_domain is None:
            raise PromotionDenied("verified failure-domain evidence is required")
        if source_domain==target_domain:
            raise PromotionDenied("source and target share a failure domain")
        if not evidence.state_verified: raise PromotionDenied("durable state is not verified")
        if not evidence.source_fenced: raise PromotionDenied("source authority is not fenced")
        if not evidence.witness_quorum: raise PromotionDenied("independent witness quorum is absent")
