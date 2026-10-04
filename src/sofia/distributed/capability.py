"""Cognitive tools for authenticated remote Fleet observation and governed changes."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
import os
from pathlib import Path
from typing import Any,Callable
from uuid import UUID,uuid4

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.safe.operator_stop import OperatorStopStore

from .authorization import remote_operation_is_read_only
from .endpoint_policy_durable import DurableEndpointPolicy
from .https_transport import PinnedHttpsRemoteTransport
from .operations import RemoteOperationRequest
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

    def invoke(self,node_id_text:str,capability:str,operation:str,parameters:dict[str,Any])->dict[str,Any]:
        if capability not in {
            "system.inspect","vm.inspect","container.inspect","llm.inspect"
        } and self._operator_stop.current().active:
            raise PermissionError("operator stop is active")
        node_id=UUID(node_id_text)
        now=datetime.now(timezone.utc)
        timeout_seconds=10.0
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
            request=RemoteOperationRequest(
                uuid4(),
                node_id,
                grant.grant_id,
                capability,
                operation,
                parameters,
            )
            result=control.invoke(
                enrollment,
                endpoint,
                request,
                now=now,
            )
        return {
            "request_id":str(result.request_id),
            "node_id":str(result.node_id),
            "outcome":result.outcome.value,
            "message":result.message,
        }

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
            return service.invoke(p["node_id"],remote_capability,remote_operation,params)
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
        _registration(service,capability_name="remote.container.restart",tool_name="restart_remote_container",
            description="Restart one exact remote container. Requires an active exact human grant.",
            remote_capability="container.manage",remote_operation="restart",
            properties={**node,"container":{"type":"string"},"timeout_seconds":{"type":"integer"}},required=("node_id","container")),
    )
