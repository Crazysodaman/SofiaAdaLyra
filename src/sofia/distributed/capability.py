"""Cognitive tools for authenticated, exact-grant remote fleet operations."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timezone,timedelta
import os
from pathlib import Path
from typing import Any,Callable
from uuid import UUID,uuid4

from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding

from .endpoint_policy_durable import DurableEndpointPolicy
from .https_transport import PinnedHttpsRemoteTransport
from .operations import RemoteOperationRequest
from .remote_control import DurableRemoteControl

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
        base=state_path.parent
        self._endpoint_lookup=DurableEndpointPolicy(base/"remote-endpoints.db")
        transport=PinnedHttpsRemoteTransport(
            self._endpoint_lookup.get,
            ca_file=ca_file,
            client_certificate=client_certificate,
            client_private_key=client_private_key,
        )
        self.control=DurableRemoteControl(
            transport=transport,
            identity_path=base/"remote-identities.db",
            endpoint_path=base/"remote-endpoints.db",
            authorization_path=base/"remote-grants.db",
            ledger_path=base/"remote-ledger.db",
            max_inventory_age=max_inventory_age,
        )

    def nodes(self)->tuple[dict[str,Any],...]:
        now=datetime.now(timezone.utc)
        out=[]
        for enrollment in self.control.identities.active():
            endpoint=self.control.endpoints.get(enrollment.node.node_id)
            grants=self.control.authorization.active_grants_for_node(enrollment.node.node_id,now=now)
            out.append({
                "node_id":str(enrollment.node.node_id),
                "name":enrollment.node.name,
                "endpoint":None if endpoint is None else {
                    "hostname":endpoint.hostname,"port":endpoint.port,"transport":endpoint.transport.value,
                },
                "authorized_operations":tuple(
                    {"capability":g.capability,"operation":g.operation,"expires_at":g.expires_at.isoformat()}
                    for g in grants
                ),
            })
        return tuple(out)

    def invoke(self,node_id_text:str,capability:str,operation:str,parameters:dict[str,Any])->dict[str,Any]:
        node_id=UUID(node_id_text)
        now=datetime.now(timezone.utc)
        enrollment=self.control.identities.get(node_id)
        if enrollment is None: raise PermissionError("node is not actively enrolled")
        endpoint=self.control.endpoints.get(node_id)
        if endpoint is None: raise PermissionError("node has no active approved endpoint")
        grant=self.control.authorization.find_active(node_id=node_id,capability=capability,operation=operation,now=now)
        if grant is None: raise PermissionError("no active exact-scope human grant for remote operation")
        request=RemoteOperationRequest(uuid4(),node_id,grant.grant_id,capability,operation,parameters)
        result=self.control.invoke(enrollment,endpoint,request,now=now)
        return {
            "request_id":str(result.request_id),
            "node_id":str(result.node_id),
            "outcome":result.outcome.value,
            "message":result.message,
        }

    def close(self)->None:
        self.control.close()
        self._endpoint_lookup.close()

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
    )
    return RemoteToolRegistration(cap,handler,binding)

def create_configured_remote_fleet_tools(state_path:Path)->tuple[RemoteToolRegistration,...]:
    values={
        "ca":os.environ.get("SOFIA_REMOTE_CA","").strip(),
        "cert":os.environ.get("SOFIA_REMOTE_CLIENT_CERT","").strip(),
        "key":os.environ.get("SOFIA_REMOTE_CLIENT_KEY","").strip(),
    }
    if not any(values.values()): return ()
    if not all(values.values()): raise ValueError("SOFIA_REMOTE_CA, SOFIA_REMOTE_CLIENT_CERT and SOFIA_REMOTE_CLIENT_KEY must be configured together")
    age=int(os.environ.get("SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS","300"))
    service=RemoteFleetToolService(
        state_path,
        ca_file=Path(values["ca"]),client_certificate=Path(values["cert"]),
        client_private_key=Path(values["key"]),max_inventory_age=timedelta(seconds=age),
    )
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
            description="List Hyper-V VMs on an enrolled remote node. Read-only when granted.",
            remote_capability="vm.inspect",remote_operation="list",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.vm.get",tool_name="inspect_remote_vm",
            description="Inspect one Hyper-V VM on an enrolled remote node. Read-only when granted.",
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
        _registration(service,capability_name="remote.container.list",tool_name="list_remote_containers",
            description="List containers through the configured agent-side Portainer endpoint. Read-only when granted.",
            remote_capability="container.inspect",remote_operation="list",properties=node,required=("node_id",)),
        _registration(service,capability_name="remote.container.get",tool_name="inspect_remote_container",
            description="Inspect one container through the configured agent-side Portainer endpoint. Read-only when granted.",
            remote_capability="container.inspect",remote_operation="get",
            properties={**node,"container":{"type":"string"}},required=("node_id","container")),
        _registration(service,capability_name="remote.container.restart",tool_name="restart_remote_container",
            description="Restart one exact remote container. Requires an active exact human grant.",
            remote_capability="container.manage",remote_operation="restart",
            properties={**node,"container":{"type":"string"},"timeout_seconds":{"type":"integer"}},required=("node_id","container")),
    )
