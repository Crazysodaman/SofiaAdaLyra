"""Authenticated-evidence bridge from NET enrollment into OPS fleet trust."""
from __future__ import annotations
from dataclasses import dataclass,replace
from datetime import datetime
from uuid import UUID
from sofia.distributed.identity import NodeEnrollment
from .fleet import FleetRegistry
from .model import FleetHost,HostLifecycle

@dataclass(frozen=True)
class MachineNodeBinding:
    host_id:str; node_id:UUID; verified_at:datetime; source:str
    def __post_init__(self):
        if not self.host_id.strip() or not self.source.strip(): raise ValueError("machine/node binding evidence required")
        if self.verified_at.tzinfo is None: raise ValueError("verified_at must be timezone-aware")

@dataclass(frozen=True)
class AuthenticatedPeerEvidence:
    node_id:UUID; public_key_sha256:str; observed_at:datetime; verifier:str
    def __post_init__(self):
        if len(self.public_key_sha256)!=64: raise ValueError("peer key fingerprint must be SHA-256")
        if self.observed_at.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
        if not self.verifier.strip(): raise ValueError("independent verifier identity required")

class FleetEnrollmentService:
    def __init__(self,registry:FleetRegistry)->None: self.registry=registry
    def enroll(self,candidate:FleetHost,*,binding:MachineNodeBinding,enrollment:NodeEnrollment,peer:AuthenticatedPeerEvidence)->FleetHost:
        if candidate.lifecycle is not HostLifecycle.CANDIDATE: raise ValueError("fleet enrollment starts from a candidate")
        if candidate.host_id!=binding.host_id: raise PermissionError("binding is for a different machine")
        if binding.node_id!=enrollment.node.node_id or peer.node_id!=enrollment.node.node_id:
            raise PermissionError("machine binding, enrollment and authenticated peer disagree")
        if peer.public_key_sha256!=enrollment.public_key_sha256:
            raise PermissionError("authenticated peer key does not match enrolled key pin")
        trusted=replace(candidate,trusted=True)
        self.registry.register_candidate(trusted)
        return self.registry.transition(trusted.host_id,HostLifecycle.ENROLLED)
