"""Capability registrations and cognitive bindings for configured integrations."""
from __future__ import annotations
import os,platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any,Callable
from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from .github import GitHubAdapter
from .home_assistant import HomeAssistantAdapter
from .hyperv import HyperVAdapter
from .jmri import JmriAdapter
from .portainer import PortainerAdapter
from .sqlite import SQLiteReadAdapter
from .storage import StorageAdapter

@dataclass(frozen=True)
class IntegrationToolRegistration:
    capability:Capability
    handler:Callable[[CapabilityRequest],Any]
    binding:CognitiveToolBinding

def _tool(name:str,description:str,parameters:dict[str,Any],handler:Callable[[dict[str,Any]],Any])->IntegrationToolRegistration:
    capability=Capability(name=name,description=description)
    def execute(request:CapabilityRequest):
        if request.capability.name!=name: raise ValueError("capability mismatch")
        return handler(dict(request.parameters))
    binding=CognitiveToolBinding(
        definition=CognitiveToolDefinition(name=name.replace(".","_"),description=description,parameters=parameters),
        capability_name=name,
    )
    return IntegrationToolRegistration(capability,execute,binding)

def _object(properties:dict[str,Any]|None=None,required:list[str]|None=None)->dict[str,Any]:
    return {"type":"object","properties":properties or {},"required":required or [],"additionalProperties":False}

def create_configured_integration_tools(*,filesystem_root:Path,state_path:Path)->tuple[IntegrationToolRegistration,...]:
    tools=[]

    ha_url=os.environ.get("SOFIA_HOME_ASSISTANT_URL","").strip()
    ha_token=os.environ.get("SOFIA_HOME_ASSISTANT_TOKEN","").strip()
    if ha_url and ha_token:
        ha=HomeAssistantAdapter(ha_url,ha_token)
        tools.extend((
            _tool("home_assistant.states","List Home Assistant entity states. Read-only.",_object(),
                lambda p:ha.states()),
            _tool("home_assistant.state","Read one Home Assistant entity state. Read-only.",
                _object({"entity_id":{"type":"string"}},["entity_id"]),
                lambda p:ha.state(p["entity_id"])),
            _tool("home_assistant.service.call","Call one explicitly named Home Assistant service.",
                _object({"domain":{"type":"string"},"service":{"type":"string"},"service_data":{"type":"object"}},["domain","service"]),
                lambda p:ha.call_service(p["domain"],p["service"],p.get("service_data"))),
        ))

    port_url=os.environ.get("SOFIA_PORTAINER_URL","").strip()
    port_key=os.environ.get("SOFIA_PORTAINER_API_KEY","").strip()
    port_endpoint=os.environ.get("SOFIA_PORTAINER_ENDPOINT_ID","").strip()
    if port_url and port_key and port_endpoint:
        port=PortainerAdapter(port_url,port_key,int(port_endpoint))
        tools.extend((
            _tool("portainer.containers","List Docker containers through Portainer. Read-only.",_object(),
                lambda p:port.containers()),
            _tool("portainer.container","Inspect one Docker container through Portainer. Read-only.",
                _object({"container_id":{"type":"string"}},["container_id"]),
                lambda p:port.container(p["container_id"])),
            _tool("portainer.container.restart","Restart one explicitly named Docker container through Portainer.",
                _object({"container_id":{"type":"string"},"timeout_seconds":{"type":"integer"}},["container_id"]),
                lambda p:port.restart(p["container_id"],timeout_seconds=p.get("timeout_seconds",10))),
        ))

    jmri_url=os.environ.get("SOFIA_JMRI_URL","").strip()
    if jmri_url:
        jmri=JmriAdapter(jmri_url)
        tools.extend((
            _tool("jmri.power","Read JMRI track-power state. Read-only.",_object(),lambda p:jmri.power()),
            _tool("jmri.roster","Read the JMRI locomotive roster. Read-only.",_object(),lambda p:jmri.roster()),
            _tool("jmri.object","Read one typed JMRI object. Read-only.",
                _object({"object_type":{"type":"string"},"name":{"type":"string"}},["object_type","name"]),
                lambda p:jmri.object(p["object_type"],p["name"])),
            _tool("jmri.power.set","Set JMRI track power for an explicitly named connection.",
                _object({"name":{"type":"string"},"state":{"type":"integer"},"prefix":{"type":"string"}},["name","state"]),
                lambda p:jmri.set_power(p["name"],p["state"],prefix=p.get("prefix"))),
        ))

    gh_repo=os.environ.get("SOFIA_GITHUB_REPOSITORY","").strip()
    if gh_repo:
        gh=GitHubAdapter(gh_repo,os.environ.get("SOFIA_GITHUB_TOKEN","").strip() or None)
        tools.extend((
            _tool("github.repository","Read configured GitHub repository metadata. Read-only.",_object(),lambda p:gh.repository_info()),
            _tool("github.issues","List configured GitHub repository issues. Read-only.",
                _object({"state":{"type":"string"},"limit":{"type":"integer"}}),
                lambda p:gh.issues(state=p.get("state","open"),limit=p.get("limit",30))),
            _tool("github.file","Read configured GitHub repository file metadata/content response. Read-only.",
                _object({"path":{"type":"string"},"ref":{"type":"string"}},["path"]),
                lambda p:gh.file(p["path"],ref=p.get("ref"))),
            _tool("github.issue.create","Create an issue in the configured GitHub repository.",
                _object({"title":{"type":"string"},"body":{"type":"string"}},["title"]),
                lambda p:gh.create_issue(p["title"],p.get("body",""))),
        ))

    if platform.system()=="Windows":
        hv=HyperVAdapter()
        tools.extend((
            _tool("hyperv.vms","List local Hyper-V virtual machines. Read-only.",_object(),lambda p:hv.vms()),
            _tool("hyperv.vm","Inspect one local Hyper-V VM. Read-only.",_object({"name":{"type":"string"}},["name"]),lambda p:hv.vm(p["name"])),
            _tool("hyperv.vm.start","Start one explicitly named local Hyper-V VM.",_object({"name":{"type":"string"}},["name"]),lambda p:hv.start(p["name"])),
            _tool("hyperv.vm.stop","Stop one explicitly named local Hyper-V VM.",
                _object({"name":{"type":"string"},"force":{"type":"boolean"}},["name"]),
                lambda p:hv.stop(p["name"],force=bool(p.get("force",False)))),
        ))

    extra_storage=tuple(
        Path(value.strip())
        for value in os.environ.get("SOFIA_STORAGE_ROOTS","").split(os.pathsep)
        if value.strip()
    )
    storage_roots=tuple(dict.fromkeys((filesystem_root,state_path.parent,*extra_storage)))
    storage=StorageAdapter(storage_roots)
    tools.append(_tool("storage.usage","Inspect disk usage for Sofía's repository/state roots. Read-only.",_object(),lambda p:storage.usage()))

    if state_path.exists():
        sqlite=SQLiteReadAdapter(state_path)
        tools.extend((
            _tool("sqlite.state.tables","List tables in Sofía's local SQLite state database. Read-only.",_object(),lambda p:sqlite.tables()),
            _tool("sqlite.state.query","Run a bounded read-only query against Sofía's state database.",
                _object({"sql":{"type":"string"},"limit":{"type":"integer"}},["sql"]),
                lambda p:sqlite.query(p["sql"],limit=p.get("limit",200))),
        ))

    return tuple(tools)
