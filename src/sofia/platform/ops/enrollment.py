"""Authenticated-evidence bridge from NET enrollment into OPS fleet trust."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timezone, timedelta
from uuid import UUID
from re import fullmatch
from typing import Callable
from sofia.platform.distributed.model import NodeEnrollment, NodeEndpoint, ApprovedEndpoint, NodeTransport
from contextlib import closing, ExitStack
from sofia.platform.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.platform.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.model import StateKey, StateRecord, StateClass
from .state_registry import StatePlaneFleetRegistry
from .fleet import FleetRegistry
from .model import FleetHost,HostLifecycle

@dataclass(frozen=True)
class MachineNodeBinding:
    host_id:str; node_id:UUID; verified_at:datetime; source:str
    def __post_init__(self):
        if not self.host_id.strip() or not self.source.strip(): raise ValueError("machine/node binding evidence required")
        if self.verified_at.tzinfo is None: raise ValueError("verified_at must be timezone-aware")

@dataclass(frozen=True)
class FleetEnrollmentApproval:
    """Untrusted reference to an exact approval; never authentication evidence."""
    approval_id:str
    host_id:str
    node_id:UUID
    public_key_sha256:str
    approved_by:str
    approved_at:datetime

    def __post_init__(self):
        if not isinstance(self.approval_id,str) or not self.approval_id.strip():
            raise ValueError("approval_id is required")
        if not isinstance(self.host_id,str) or not self.host_id.strip():
            raise ValueError("host_id is required")
        if not isinstance(self.node_id,UUID):
            raise TypeError("node_id must be UUID")
        if fullmatch(r"[0-9a-f]{64}",self.public_key_sha256) is None:
            raise ValueError("approval public key must be lowercase SHA-256")
        if not isinstance(self.approved_by,str) or not self.approved_by.strip() or len(self.approved_by)>160:
            raise ValueError("approval actor metadata must be bounded nonempty text")
        if self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None:
            raise ValueError("approved_at must be timezone-aware")


@dataclass(frozen=True)
class AuthenticatedPeerEvidence:
    node_id:UUID; public_key_sha256:str; observed_at:datetime; verifier:str
    def __post_init__(self):
        if fullmatch(r"[0-9a-f]{64}",self.public_key_sha256) is None: raise ValueError("peer key fingerprint must be lowercase SHA-256")
        if self.observed_at.tzinfo is None: raise ValueError("observed_at must be timezone-aware")
        if not self.verifier.strip(): raise ValueError("independent verifier identity required")

class FleetEnrollmentService:
    def __init__(
        self,
        registry:FleetRegistry,
        *,
        enrolled_notifier:Callable[[FleetHost,MachineNodeBinding,NodeEnrollment,AuthenticatedPeerEvidence],None]|None=None,
        clock:Callable[[],datetime]|None=None,
    )->None:
        self.registry=registry
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable or None")
        self._clock=clock if clock is not None else lambda:datetime.now(timezone.utc)
        if enrolled_notifier is not None and not callable(enrolled_notifier):
            raise TypeError("enrolled_notifier must be callable or None")
        self.enrolled_notifier=enrolled_notifier

    def set_enrolled_notifier(
        self,
        notifier:Callable[[FleetHost,MachineNodeBinding,NodeEnrollment,AuthenticatedPeerEvidence],None]|None,
    )->None:
        if notifier is not None and not callable(notifier):
            raise TypeError("notifier must be callable or None")
        self.enrolled_notifier=notifier

    @staticmethod
    def _discovery_parameters(candidate:FleetHost)->tuple[dict,datetime]:
        values={}
        for name in ("observed-node", "observed-key", "observed-endpoint-host", "observed-endpoint-port", "observed-at"):
            matches=[tag[len(name)+1:] for tag in candidate.tags if tag.startswith(name+":")]
            if len(matches)!=1 or not matches[0]:
                raise PermissionError("Fleet candidate lacks exact verified discovery evidence")
            values[name]=matches[0]
        if "capabilities-verified" not in candidate.tags:
            raise PermissionError("Fleet candidate lacks verified capability evidence")
        try:
            observed=datetime.fromisoformat(values["observed-at"])
            endpoint_port=int(values["observed-endpoint-port"])
            node_id=str(UUID(values["observed-node"]))
        except (TypeError,ValueError) as exc:
            raise PermissionError("Fleet discovery evidence is malformed") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise PermissionError("Fleet discovery timestamp must be timezone-aware")
        return {
            "host_id":candidate.host_id,
            "node_id":node_id,
            "public_key_sha256":values["observed-key"],
            "endpoint_hostname":values["observed-endpoint-host"],
            "endpoint_port":endpoint_port,
        },observed
    def enroll(
        self,
        candidate:FleetHost,
        *,
        binding:MachineNodeBinding,
        enrollment:NodeEnrollment,
        peer:AuthenticatedPeerEvidence,
        approval:FleetEnrollmentApproval,
        endpoint:NodeEndpoint|None=None,
    )->FleetHost:
        if not isinstance(approval,FleetEnrollmentApproval):
            raise PermissionError("Fleet enrollment requires exact owner approval")
        if (
            approval.host_id!=candidate.host_id
            or approval.node_id!=enrollment.node.node_id
            or approval.public_key_sha256!=enrollment.public_key_sha256
        ):
            raise PermissionError(
                "Fleet enrollment approval does not match discovered host identity"
            )
        if candidate.lifecycle is not HostLifecycle.CANDIDATE: raise ValueError("fleet enrollment starts from a candidate")
        if candidate.trusted: raise ValueError("candidate must enter authenticated enrollment untrusted")
        if candidate.host_id!=binding.host_id: raise PermissionError("binding is for a different machine")
        if binding.node_id!=enrollment.node.node_id or peer.node_id!=enrollment.node.node_id:
            raise PermissionError("machine binding, enrollment and authenticated peer disagree")
        if peer.public_key_sha256!=enrollment.public_key_sha256:
            raise PermissionError("authenticated peer key does not match enrolled key pin")
        # A DTO, caller label, or in-memory registry cannot authorize trust.
        if not isinstance(self.registry, StatePlaneFleetRegistry) or not isinstance(self.registry.state_plane, SQLiteStatePlane):
            raise PermissionError("Fleet enrollment requires canonical transactional SQLite state")
        if not isinstance(endpoint, NodeEndpoint) or endpoint.transport is not NodeTransport.HTTPS:
            raise PermissionError("Fleet enrollment requires the exact approved HTTPS endpoint")
        expected,observed=self._discovery_parameters(candidate)
        parameters={
            "host_id":candidate.host_id,"node_id":str(enrollment.node.node_id),
            "public_key_sha256":enrollment.public_key_sha256,
            "endpoint_hostname":endpoint.hostname,"endpoint_port":endpoint.port,
        }
        if parameters!=expected or any(moment!=observed for moment in (
            peer.observed_at,binding.verified_at,enrollment.provisioned_at,
        )):
            raise PermissionError("Fleet admission does not match durable discovery evidence")
        now=self._clock()
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PermissionError("Fleet host clock is unavailable")
        now=now.astimezone(timezone.utc)
        age=now-peer.observed_at.astimezone(timezone.utc)
        if age < timedelta(0) or age > timedelta(minutes=30):
            raise PermissionError("Fleet discovery evidence is future-dated or stale")
        plane=self.registry.state_plane
        verifier=ExecutionApprovalVerifier(plane.path)
        with ExitStack() as stores:
            identities=DurableNodeIdentityRegistry(plane.path)
            stores.callback(identities.close)
            endpoints=DurableEndpointPolicy(plane.path)
            stores.callback(endpoints.close)
            with plane._lock, closing(plane._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                key=StateKey(namespace=self.registry.NAMESPACE,key=candidate.host_id)
                row=db.execute("SELECT * FROM state_plane_record WHERE namespace=? AND record_key=? AND principal_id=? AND audience=?",plane._scope(key)).fetchone()
                if row is None:
                    raise PermissionError("Fleet candidate has no durable discovery record")
                current=plane._record(row)
                if self.registry._decode(current) != candidate:
                    raise PermissionError("Fleet candidate changed since discovery")
                existing=identities._get_in_transaction(db,enrollment.node.node_id)
                if existing is not None and existing.public_key_sha256 != enrollment.public_key_sha256:
                    raise PermissionError("Fleet node identity differs from approved discovery evidence")
                recorded_endpoint=endpoints._get_in_transaction(db,enrollment.node.node_id)
                if recorded_endpoint is not None and recorded_endpoint != endpoint:
                    raise PermissionError("Fleet endpoint differs from approved discovery evidence")
                verified=verifier.consume(approval_id=approval.approval_id,capability="fleet.enroll",parameters=parameters,now=now,_transaction_db=db)
                accepted_enrollment=replace(enrollment,recorded_by=verified.principal_id)
                if existing is None:
                    identities._enroll_in_transaction(db,accepted_enrollment)
                if recorded_endpoint is None:
                    endpoints._approve_in_transaction(db,ApprovedEndpoint(enrollment.node.node_id,endpoint,verified.principal_id))
                enrolled=replace(candidate,trusted=True,node_id=enrollment.node.node_id,lifecycle=HostLifecycle.ENROLLED)
                plane._write_one(db,StateRecord(key=key,state_class=StateClass.SHARED_AUTHORITATIVE,
                    revision=current.revision+1,value=self.registry._encode(enrolled),updated_at=now,
                    source="ops:fleet:authenticated-enrollment"),current.revision)
                verifier.audit.append_in_transaction(
                    db,actor_id=verified.principal_id,event_type="fleet.enrolled",
                    payload={**parameters,"approval_id":verified.approval_id,
                        "registry_revision":current.revision+1},
                    occurred_at=now,event_id=f"fleet-enrollment:{verified.approval_id}",
                )
            # Publish cache and notify only after every owner has committed.
            self.registry._hosts[candidate.host_id]=enrolled
        if self.enrolled_notifier is not None:
            self.enrolled_notifier(enrolled,binding,accepted_enrollment,peer)
        return enrolled
