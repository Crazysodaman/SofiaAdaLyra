"""Cognitive tools for authenticated remote Fleet observation and governed changes."""
from __future__ import annotations
from contextlib import closing,contextmanager
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
import os
from pathlib import Path
from time import perf_counter
from hashlib import sha256
from typing import Any,Callable
from uuid import UUID,uuid4

from sofia.platform.capability.model import Capability,CapabilityRequest
from sofia.core.cognition.model import CognitiveToolDefinition
from sofia.core.cognition.tools import CognitiveToolBinding
from sofia.platform.ops.model import HostLifecycle
from sofia.platform.ops.latency import FleetLatencyStore
from sofia.platform.ops.state_registry import StatePlaneFleetRegistry
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.core.goals.evidence import GoalEvidence, GoalEvidenceLedger
from sofia.core.goals.service import audience_scope
from sofia.core.social.model import PrincipalContext

from .authorization import remote_operation_is_read_only
from .endpoint_policy_durable import DurableEndpointPolicy
from .https_transport import PinnedHttpsRemoteTransport
from .operations import (
    RemoteOperationRequest, RemoteOperationUncertain, RemoteOutcome,
)
from .remote_control import DurableRemoteControl
from .state_paths import migrate_legacy_fleet_sidecars

@dataclass(frozen=True)
class RemoteToolRegistration:
    capability:Capability
    handler:Callable[[CapabilityRequest],Any]
    binding:CognitiveToolBinding

class RemoteFleetToolService:
    def __init__(
        self,
        state_path:Path,
        *,
        ca_file:Path,
        client_certificate:Path,
        client_private_key:Path,
        max_inventory_age:timedelta=timedelta(minutes=5),
    )->None:
        self._state_path=Path(state_path)
        migrate_legacy_fleet_sidecars(self._state_path)
        self._ca_file=Path(ca_file)
        self._client_certificate=Path(client_certificate)
        self._client_private_key=Path(client_private_key)
        self._max_inventory_age=max_inventory_age
        self._operator_stop=OperatorStopStore(self._state_path)
        self._latency=FleetLatencyStore(self._state_path)
        self._guard=CanonicalSQLiteGuard(self._state_path)
        with closing(self._guard.connect(timeout=10)) as db,db:
            db.execute("""CREATE TABLE IF NOT EXISTS fleet_goal_dispatch(
                dispatch_id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                audience TEXT NOT NULL,
                node_id TEXT NOT NULL,
                request_id TEXT NOT NULL UNIQUE,
                remote_capability TEXT NOT NULL,
                remote_operation TEXT NOT NULL,
                reserved_at TEXT NOT NULL
            )""")

    def _ops_host_for_node(self, node_id: UUID):
        """Return the active trusted OPS Fleet host bound to this node."""
        registry = StatePlaneFleetRegistry(
            SQLiteStatePlane(self._state_path),
            legacy_path=self._state_path.parent / "fleet.json",
        )
        matches = tuple(
            host
            for host in registry.hosts()
            if host.node_id == node_id
        )
        if len(matches) != 1:
            return None
        host = matches[0]
        if (
            not host.trusted
            or host.lifecycle
            in {HostLifecycle.CANDIDATE, HostLifecycle.DECOMMISSIONED}
        ):
            return None
        return host

    @contextmanager
    def _control_session(self, *, timeout_seconds: float = 10.0):
        """Open durable Fleet state only for the lifetime of one tool call."""
        endpoint_lookup=DurableEndpointPolicy(
            self._state_path
        )
        transport=PinnedHttpsRemoteTransport(
            endpoint_lookup.get,
            ca_file=self._ca_file,
            client_certificate=self._client_certificate,
            client_private_key=self._client_private_key,
            timeout_seconds=timeout_seconds,
        )
        control=DurableRemoteControl(
            transport=transport,
            identity_path=self._state_path,
            endpoint_path=self._state_path,
            authorization_path=self._state_path,
            ledger_path=self._state_path,
            max_inventory_age=self._max_inventory_age,
        )
        try:
            yield control
        finally:
            control.close()
            endpoint_lookup.close()

    def nodes(self)->tuple[dict[str,Any],...]:
        now=datetime.now(timezone.utc)
        out=[]
        with self._control_session() as control:
            for enrollment in control.identities.active():
                if self._ops_host_for_node(enrollment.node.node_id) is None:
                    continue
                endpoint=control.endpoints.get(enrollment.node.node_id)
                grants=control.authorization.active_grants_for_node(
                    enrollment.node.node_id,
                    now=now,
                )
                out.append({
                    "node_id":str(enrollment.node.node_id),
                    "name":enrollment.node.name,
                    "endpoint":None if endpoint is None else {
                        "hostname":endpoint.hostname,
                        "port":endpoint.port,
                        "transport":endpoint.transport.value,
                    },
                    "authorized_operations":tuple(
                        {
                            "capability":g.capability,
                            "operation":g.operation,
                            "expires_at":g.expires_at.isoformat(),
                        }
                        for g in grants
                    ),
                })
        return tuple(out)

    def invoke(
        self,node_id_text:str,capability:str,operation:str,
        parameters:dict[str,Any],*,dispatch_context=None,
    )->dict[str,Any]:
        if capability not in {
            "system.inspect","vm.inspect","container.inspect","llm.inspect",
            "workshop.inspect",
        } and self._operator_stop.current().active:
            raise PermissionError("operator stop is active")
        node_id=UUID(node_id_text)
        ops_host=self._ops_host_for_node(node_id)
        if ops_host is None:
            raise PermissionError(
                "node is not an active trusted OPS Fleet member"
            )
        now=datetime.now(timezone.utc)
        timeout_seconds=10.0
        if capability=="workshop.network" and operation=="stage":
            timeout_seconds=180.0
        if capability=="workshop.bootstrap" and operation=="start":
            # Fully independent protected grant is still mandatory.
            # Booting verified offline media can require hashing a large ISO.
            timeout_seconds=300.0
        if capability=="workshop.inspect" and operation=="media":
            # Hashing a large approved local image may take multiple seconds.
            # This remains a bounded read-only operation; no VM is created.
            timeout_seconds=120.0
        if capability=="llm.manage":
            timeout_seconds={
                "pull":7200.0,
                "load":600.0,
                "unload":60.0,
            }.get(operation,10.0)
        with self._control_session(timeout_seconds=timeout_seconds) as control:
            enrollment=control.identities.get(node_id)
            if enrollment is None:
                raise PermissionError("node is not actively enrolled")
            endpoint=control.endpoints.get(node_id)
            if endpoint is None:
                raise PermissionError("node has no active approved endpoint")
            grant=control.authorization.find_active(
                node_id=node_id,
                capability=capability,
                operation=operation,
                now=now,
            )
            if grant is None and remote_operation_is_read_only(
                capability,
                operation,
            ):
                grant=control.authorization.ensure_read_only_policy_grant(
                    node_id=node_id,
                    capability=capability,
                    operation=operation,
                    now=now,
                )
            if grant is None:
                raise PermissionError(
                    "no active exact-scope human grant for remote change"
                )
            if capability=="workshop.bootstrap" and operation=="start":
                # Every caller, including future APIs or model paths, must
                # consume one canonical exact owner approval BEFORE transport.
                # An old/scope-only RemoteGrant is never enough to boot.
                from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
                if set(parameters)!={
                    "vm_id","disk_path","iso_path","iso_sha256",
                    "handoff_fingerprint","approval_id",
                }:
                    raise PermissionError(
                        "exact approved bootstrap fields required"
                    )
                approval_id=parameters["approval_id"]
                if not isinstance(approval_id,str) or not approval_id.strip():
                    raise PermissionError("one-use owner approval required")
                ExecutionApprovalVerifier(self._state_path).consume(
                    approval_id=approval_id,
                    capability="workshop.guest.bootstrap",
                    parameters={
                        "artemis_node_id":str(node_id),
                        "vm_id":parameters["vm_id"],
                        "disk_path":parameters["disk_path"],
                        "iso_path":parameters["iso_path"],
                        "iso_sha256":parameters["iso_sha256"],
                        "handoff_fingerprint":parameters["handoff_fingerprint"],
                    },
                    now=now,
                )
            if capability=="workshop.network" and operation=="stage":
                # Never accept a standing generic Fleet grant as permission
                # to reconfigure Artemis networking. Exact one-use SAFE
                # approval is consumed before the remote command is issued.
                from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
                from sofia.platform.ops.workshop_network import network_policy_digest
                if set(parameters)!={
                    "vm_id","network_policy_digest","approval_id",
                }:
                    raise PermissionError("exact Internal network stage fields required")
                if (
                    not isinstance(parameters.get("approval_id"),str)
                    or not parameters["approval_id"].strip()
                    or parameters["network_policy_digest"]!=network_policy_digest()
                ):
                    raise PermissionError("one-use host-only network approval mismatch")
                ExecutionApprovalVerifier(self._state_path).consume(
                    approval_id=parameters["approval_id"],
                    capability="workshop.network.create",
                    parameters={
                        "artemis_node_id":str(node_id),
                        "vm_id":parameters["vm_id"],
                        "network_policy_digest":parameters["network_policy_digest"],
                    },
                    now=now,
                )
            request=RemoteOperationRequest(
                uuid4(),
                node_id,
                grant.grant_id,
                capability,
                operation,
                parameters,
                dispatch_context,
            )
            if dispatch_context is not None:
                values=(
                    dispatch_context.dispatch_id,dispatch_context.goal_id,
                    dispatch_context.capability,dispatch_context.principal_id,
                    dispatch_context.audience,str(node_id),str(request.request_id),
                    capability,operation,now.isoformat(),
                )
                with closing(self._guard.connect(timeout=10)) as db,db:
                    cursor=db.execute(
                        "INSERT OR IGNORE INTO fleet_goal_dispatch VALUES(?,?,?,?,?,?,?,?,?,?)",
                        values,
                    )
                    if cursor.rowcount==0:
                        prior=db.execute(
                            "SELECT dispatch_id,goal_id,capability,principal_id,audience,"
                            "node_id,request_id,remote_capability,remote_operation,reserved_at "
                            "FROM fleet_goal_dispatch WHERE dispatch_id=?",
                            (dispatch_context.dispatch_id,),
                        ).fetchone()
                        if prior!=values:
                            raise PermissionError(
                                "GOALS dispatch is already bound to another remote operation"
                            )
            started=perf_counter()
            result=control.invoke(
                enrollment,
                endpoint,
                request,
                now=now,
            )
            if result.outcome is not RemoteOutcome.REPORTED_SUCCESS:
                raise RemoteOperationUncertain(
                    "remote host did not return a verified successful operation; "
                    "never retry automatically"
                )
            elapsed_ms=max((perf_counter()-started)*1000.0,0.001)
        # A telemetry write must never turn a completed external operation
        # into an apparent failure that callers might retry.  It is therefore
        # best-effort and only attempted after the gateway has authenticated
        # and identity-validated the remote result.
        latency_observation="recorded"
        try:
            self._latency.append_authenticated(
                request_id=result.request_id,
                host_id=ops_host.host_id,
                node_id=result.node_id,
                capability=capability,
                operation=operation,
                outcome=result.outcome.value,
                elapsed_ms=elapsed_ms,
                observed_at=datetime.now(timezone.utc),
            )
        except Exception:
            latency_observation="unavailable"
        return {
            "request_id":str(result.request_id),
            "node_id":str(result.node_id),
            "outcome":result.outcome.value,
            "message":result.message,
            "latency_observation":latency_observation,
        }

    def verify_goal_dispatch(self,dispatch_id:str,evidence)->bool:
        """Verify an exact GOALS receipt against its pinned host observation."""
        if not isinstance(dispatch_id,str) or not dispatch_id.strip():
            return False
        with closing(self._guard.connect(timeout=10,read_only=True)) as db:
            row=db.execute(
                "SELECT goal_id,capability,principal_id,audience,node_id,reserved_at "
                "FROM fleet_goal_dispatch WHERE dispatch_id=?",
                (dispatch_id,),
            ).fetchone()
        if row is None or (
            row[0]!=getattr(evidence,"goal_id",None)
            or row[1]!=getattr(evidence,"assertion",None)
            or row[2]!=getattr(evidence,"principal_id",None)
            or row[3]!=getattr(evidence,"audience",None)
        ):
            return False
        node_id=UUID(row[4])
        if self._ops_host_for_node(node_id) is None:
            return False
        with self._control_session() as control:
            enrollment=control.identities.get(node_id)
            endpoint=control.endpoints.get(node_id)
            if enrollment is None or endpoint is None:
                return False
            attestation=control.host_effect(enrollment,endpoint,dispatch_id)
        try:
            observed=datetime.fromisoformat(attestation["observed_at"])
        except (KeyError,TypeError,ValueError):
            return False
        evidence_time=getattr(evidence,"observed_at",None)
        moment=datetime.now(timezone.utc)
        expected="performed" if getattr(evidence,"successful",None) is True else (
            "absent" if getattr(evidence,"successful",None) is False else None
        )
        return bool(
            expected is not None
            and attestation.get("dispatch_id")==dispatch_id
            and attestation.get("goal_id")==row[0]
            and attestation.get("capability")==row[1]
            and attestation.get("outcome")==expected
            and attestation.get("attested_by")==f"fleet-node:{node_id}"
            and isinstance(evidence_time,datetime)
            and evidence_time.tzinfo is not None
            and observed==evidence_time
            and datetime.fromisoformat(row[5])<=observed<=moment
            and observed>=moment-timedelta(minutes=15)
        )

    def observe_goal_dispatch(
        self,dispatch_id:str,*,principal:PrincipalContext,now:datetime,
    )->GoalEvidence:
        """Project one pinned-host observation into typed scoped GOALS evidence."""
        if not isinstance(principal,PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        if not isinstance(now,datetime) or now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        with closing(self._guard.connect(timeout=10,read_only=True)) as db:
            row=db.execute(
                "SELECT goal_id,capability,principal_id,audience,node_id,reserved_at "
                "FROM fleet_goal_dispatch WHERE dispatch_id=?",
                (dispatch_id,),
            ).fetchone()
        if row is None:
            raise LookupError("exact remote GOALS dispatch was not reserved")
        if (
            row[2]!=principal.principal_id
            or row[3]!=audience_scope(principal)
        ):
            raise PermissionError("host outcome scope does not match principal")
        node_id=UUID(row[4])
        if self._ops_host_for_node(node_id) is None:
            raise PermissionError("attesting Fleet node is not active and trusted")
        with self._control_session() as control:
            enrollment=control.identities.get(node_id)
            endpoint=control.endpoints.get(node_id)
            if enrollment is None or endpoint is None:
                raise PermissionError("attesting Fleet identity is not active")
            attestation=control.host_effect(enrollment,endpoint,dispatch_id)
        if (
            attestation.get("goal_id")!=row[0]
            or attestation.get("capability")!=row[1]
            or attestation.get("attested_by")!=f"fleet-node:{node_id}"
            or attestation.get("outcome") not in {"performed","absent"}
        ):
            raise ValueError("host outcome does not match exact GOALS dispatch")
        try:
            observed=datetime.fromisoformat(attestation["observed_at"])
        except (KeyError,TypeError,ValueError) as exc:
            raise ValueError("host outcome has invalid observation time") from exc
        moment=now.astimezone(timezone.utc)
        if (
            observed.tzinfo is None
            or observed<datetime.fromisoformat(row[5])
            or observed>moment
            or observed<moment-timedelta(minutes=15)
        ):
            raise ValueError("host outcome is stale, future, or predates dispatch")
        digest=sha256(
            f"{node_id}\0{dispatch_id}\0{attestation['outcome']}\0"
            f"{observed.isoformat()}".encode()
        ).hexdigest()
        return GoalEvidenceLedger(self._state_path).record(
            evidence_ref=f"goal-evidence:fleet-host-effect:{digest}",
            kind="operation_receipt",observed_at=observed,
            source=f"fleet-host-effect:{node_id}",
            successful=attestation["outcome"]=="performed",
            goal_id=row[0],action_id=dispatch_id,assertion=row[1],
            principal_id=principal.principal_id,audience=audience_scope(principal),
            payload={"node_id":str(node_id),"attested_by":attestation["attested_by"]},
        )

    def close(self)->None:
        """Compatibility no-op: production Fleet sessions are per-call."""
        return None

def _registration(
    service:RemoteFleetToolService,
    *,
    capability_name:str,
    tool_name:str,
    description:str,
    remote_capability:str|None=None,
    remote_operation:str|None=None,
    properties:dict[str,Any]|None=None,
    required:tuple[str,...]=(),
    parameter_builder:Callable[[dict[str,Any]],dict[str,Any]]|None=None,
)->RemoteToolRegistration:
    cap=Capability(capability_name,description)
    if capability_name=="remote.nodes":
        handler=lambda request:service.nodes()
    else:
        if remote_capability is None or remote_operation is None: raise ValueError("remote mapping required")
        def handler(request):
            p=dict(request.parameters)
            params=parameter_builder(p) if parameter_builder else {k:v for k,v in p.items() if k!="node_id"}
            if request.dispatch_context is None:
                return service.invoke(
                    p["node_id"],remote_capability,remote_operation,params,
                )
            return service.invoke(
                p["node_id"],remote_capability,remote_operation,params,
                dispatch_context=request.dispatch_context,
            )
    binding=CognitiveToolBinding(
        definition=CognitiveToolDefinition(
            name=tool_name,description=description,
            parameters={"type":"object","properties":properties or {},"required":list(required),"additionalProperties":False},
        ),
        capability_name=capability_name,
        produces_execution_receipt=(
            remote_capability is not None
            and remote_capability.endswith(".manage")
        ),
        execution_receipt_evidence_match=(
            ("outcome", "reported_success")
            if (
                remote_capability is not None
                and remote_capability.endswith(".manage")
            )
            else None
        ),
    )
    return RemoteToolRegistration(cap,handler,binding)

def create_configured_remote_fleet_service(
    state_path:Path,
)->RemoteFleetToolService|None:
    values={
        "ca":os.environ.get("SOFIA_REMOTE_CA","").strip(),
        "cert":os.environ.get("SOFIA_REMOTE_CLIENT_CERT","").strip(),
        "key":os.environ.get("SOFIA_REMOTE_CLIENT_KEY","").strip(),
    }
    if not any(values.values()):
        return None
    if not all(values.values()):
        raise ValueError(
            "SOFIA_REMOTE_CA, SOFIA_REMOTE_CLIENT_CERT and "
            "SOFIA_REMOTE_CLIENT_KEY must be configured together"
        )
    age=int(os.environ.get("SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS","300"))
    return RemoteFleetToolService(
        state_path,
        ca_file=Path(values["ca"]),
        client_certificate=Path(values["cert"]),
        client_private_key=Path(values["key"]),
        max_inventory_age=timedelta(seconds=age),
    )


def create_configured_remote_fleet_tools(state_path:Path)->tuple[RemoteToolRegistration,...]:
    service=create_configured_remote_fleet_service(state_path)
    if service is None:
        return ()
    node={"node_id":{"type":"string"}}
    exact=lambda keys:(lambda p:{k:p[k] for k in keys if k in p})
    return (
        _registration(service,capability_name="remote.nodes",tool_name="list_remote_nodes",
            description="List actively enrolled remote nodes, approved endpoints and currently authorized exact operations. Read-only."),
        _registration(service,capability_name="remote.process.inspect",tool_name="inspect_remote_processes",
            description="Inspect processes on one enrolled remote node through pinned mTLS.",
            remote_capability="system.inspect",remote_operation="process",
            properties={**node,"pid":{"type":"integer"},"limit":{"type":"integer"}},required=("node_id",)),
        _registration(service,capability_name="remote.system.inspect",tool_name="inspect_remote_system",
            description="Inspect system state on one enrolled remote node through pinned mTLS.",
            remote_capability="system.inspect",remote_operation="system",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.network.inspect",tool_name="inspect_remote_network",
            description="Inspect network state on one enrolled remote node through pinned mTLS.",
            remote_capability="system.inspect",remote_operation="network",
            properties={**node,"interface":{"type":"string"},"limit":{"type":"integer"}},required=("node_id",)),
        _registration(service,capability_name="remote.service.inspect",tool_name="inspect_remote_services",
            description="Inspect services on one enrolled remote node through pinned mTLS.",
            remote_capability="system.inspect",remote_operation="service",
            properties={**node,"name":{"type":"string"},"state":{"type":"string"},"limit":{"type":"integer"}},required=("node_id",)),
        _registration(service,capability_name="remote.hardware.inspect",tool_name="inspect_remote_hardware",
            description="Inspect hardware on one enrolled remote node through pinned mTLS.",
            remote_capability="system.inspect",remote_operation="hardware",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.service.start",tool_name="start_remote_service",
            description="Start one exact service on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="service.manage",remote_operation="start",
            properties={**node,"service":{"type":"string"}},required=("node_id","service")),
        _registration(service,capability_name="remote.service.stop",tool_name="stop_remote_service",
            description="Stop one exact service on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="service.manage",remote_operation="stop",
            properties={**node,"service":{"type":"string"}},required=("node_id","service")),
        _registration(service,capability_name="remote.service.restart",tool_name="restart_remote_service",
            description="Restart one exact service on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="service.manage",remote_operation="restart",
            properties={**node,"service":{"type":"string"}},required=("node_id","service")),
        _registration(service,capability_name="remote.host.reboot",tool_name="reboot_remote_host",
            description="Reboot one enrolled remote node. Requires an active exact human grant.",
            remote_capability="system.manage",remote_operation="reboot",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.package.update",tool_name="update_remote_package",
            description="Update one exact package on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="package.manage",remote_operation="update",
            properties={**node,"package":{"type":"string"}},required=("node_id","package")),
        _registration(service,capability_name="remote.vm.list",tool_name="list_remote_vms",
            description="List Hyper-V VMs on an enrolled remote node. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="vm.inspect",remote_operation="list",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.vm.get",tool_name="inspect_remote_vm",
            description="Inspect one Hyper-V VM on an enrolled remote node. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="vm.inspect",remote_operation="get",
            properties={**node,"vm":{"type":"string"}},required=("node_id","vm")),
        _registration(service,capability_name="remote.vm.sofia.inspect",tool_name="inspect_remote_sofia_guest",
            description="Inspect the reserved Sofia VM on an enrolled Hyper-V host, returning read-only readiness blockers without claiming Debian OS or writer activation.",
            remote_capability="vm.inspect",remote_operation="sofia_preflight",
            properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.vm.start",tool_name="start_remote_vm",
            description="Start one exact Hyper-V VM on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="vm.manage",remote_operation="start",
            properties={**node,"vm":{"type":"string"}},required=("node_id","vm")),
        _registration(service,capability_name="remote.vm.stop",tool_name="stop_remote_vm",
            description="Stop one exact Hyper-V VM on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="vm.manage",remote_operation="stop",
            properties={**node,"vm":{"type":"string"},"force":{"type":"boolean"}},required=("node_id","vm")),
        _registration(service,capability_name="remote.ollama.inference_policy",tool_name="inspect_remote_ollama_inference_policy",
            description="Read the exact Ollama model allowlist accepted for cognitive inference on one enrolled remote node.",
            remote_capability="llm.inspect",remote_operation="inference_policy",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.ollama.models",tool_name="list_remote_ollama_models",
            description="List installed Ollama models on one enrolled remote node. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="llm.inspect",remote_operation="models",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.ollama.running",tool_name="list_remote_running_models",
            description="List resident Ollama models on one enrolled remote node. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="llm.inspect",remote_operation="running",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.ollama.show",tool_name="inspect_remote_ollama_model",
            description="Inspect one exact Ollama model on an enrolled remote node. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="llm.inspect",remote_operation="show",
            properties={**node,"model":{"type":"string"}},required=("node_id","model")),
        _registration(service,capability_name="remote.ollama.pull",tool_name="install_remote_ollama_model",
            description="Install or update one exact Ollama model on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="llm.manage",remote_operation="pull",
            properties={**node,"model":{"type":"string"}},required=("node_id","model")),
        _registration(service,capability_name="remote.ollama.load",tool_name="load_remote_ollama_model",
            description="Load one exact installed Ollama model on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="llm.manage",remote_operation="load",
            properties={**node,"model":{"type":"string"},"keep_alive":{"type":"string"}},required=("node_id","model")),
        _registration(service,capability_name="remote.ollama.unload",tool_name="unload_remote_ollama_model",
            description="Unload one exact Ollama model on an enrolled remote node. Requires an active exact human grant.",
            remote_capability="llm.manage",remote_operation="unload",
            properties={**node,"model":{"type":"string"}},required=("node_id","model")),
        _registration(service,capability_name="remote.container.list",tool_name="list_remote_containers",
            description="List containers through the configured agent-side Portainer endpoint. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="container.inspect",remote_operation="list",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.get",tool_name="inspect_remote_container",
            description="Inspect one container through the configured agent-side Portainer endpoint. Read-only on an enrolled trusted node; no per-use approval.",
            remote_capability="container.inspect",remote_operation="get",
            properties={**node,"container":{"type":"string"}},required=("node_id","container")),
        _registration(service,capability_name="remote.container.stats",tool_name="inspect_remote_container_stats",
            description="Read one remote container's current resource statistics. Read-only.",
            remote_capability="container.inspect",remote_operation="stats",
            properties={**node,"container":{"type":"string"}},required=("node_id","container")),
        _registration(service,capability_name="remote.container.logs",tool_name="inspect_remote_container_logs",
            description="Read bounded recent logs from one remote Docker container. Read-only.",
            remote_capability="container.inspect",remote_operation="logs",
            properties={**node,"container":{"type":"string"},"tail":{"type":"integer"},"max_bytes":{"type":"integer"}},
            required=("node_id","container")),
        _registration(service,capability_name="remote.container.info",tool_name="inspect_remote_docker_info",
            description="Read remote Docker engine information through agent-side Portainer. Read-only.",
            remote_capability="container.inspect",remote_operation="info",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.summary",tool_name="inspect_remote_docker_summary",
            description="Read remote Docker engine/container health summary. Read-only.",
            remote_capability="container.inspect",remote_operation="summary",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.images",tool_name="list_remote_docker_images",
            description="List remote Docker images. Read-only.",
            remote_capability="container.inspect",remote_operation="images",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.volumes",tool_name="list_remote_docker_volumes",
            description="List remote Docker volumes. Read-only.",
            remote_capability="container.inspect",remote_operation="volumes",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.networks",tool_name="list_remote_docker_networks",
            description="List remote Docker networks. Read-only.",
            remote_capability="container.inspect",remote_operation="networks",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.stacks",tool_name="list_remote_portainer_stacks",
            description="List remote Portainer stacks. Read-only.",
            remote_capability="container.inspect",remote_operation="stacks",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.release.current",tool_name="inspect_remote_release",
            description="Read the active signed release identity on one enrolled remote node. Read-only.",
            remote_capability="release.inspect",remote_operation="current",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.restart",tool_name="restart_remote_container",
            description="Restart one exact remote container. Requires an active exact human grant.",
            remote_capability="container.manage",remote_operation="restart",
            properties={**node,"container":{"type":"string"},"timeout_seconds":{"type":"integer"}},required=("node_id","container")),
    )
