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
from .discord import DiscordOperatorAdapter
from .home_assistant import HomeAssistantAdapter
from .hyperv import HyperVAdapter
from .jmri import JmriAdapter
from .local_maintenance import LocalMaintenanceAdapter
from .portainer import PortainerAdapter
from .ollama import OllamaAdapter
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
        notify_service=os.environ.get("SOFIA_NOTIFICATION_HA_SERVICE","").strip()
        if notify_service:
            if "/" in notify_service or not notify_service.replace("_","").replace("-","").isalnum():
                raise ValueError("SOFIA_NOTIFICATION_HA_SERVICE must be one Home Assistant notify service name")
            tools.append(
                _tool("notification.send","Send one notification through the configured Home Assistant notify service.",
                    _object({"message":{"type":"string"},"title":{"type":"string"}},["message"]),
                    lambda p:ha.call_service("notify",notify_service,
                        {"message":p["message"],**({"title":p["title"]} if p.get("title") else {})})
            )
        tools.extend((
            _tool("home_assistant.services","List Home Assistant service domains and services. Read-only.",_object(),
                lambda p:ha.services()),
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
            _tool("portainer.endpoints","List Portainer endpoints. Read-only.",_object(),
                lambda p:port.endpoints()),
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
            _tool("github.pull_requests","List configured GitHub repository pull requests. Read-only.",
                _object({"state":{"type":"string"},"limit":{"type":"integer"}}),
                lambda p:gh.pull_requests(state=p.get("state","open"),limit=p.get("limit",30))),
            _tool("github.pull_request.create","Create a pull request in the configured GitHub repository.",
                _object({"title":{"type":"string"},"head":{"type":"string"},"base":{"type":"string"},"body":{"type":"string"},"draft":{"type":"boolean"}},["title","head","base"]),
                lambda p:gh.create_pull_request(p["title"],p["head"],p["base"],body=p.get("body",""),draft=bool(p.get("draft",False)))),
            _tool("github.pull_request.merge","Merge one configured GitHub repository pull request.",
                _object({"number":{"type":"integer"},"merge_method":{"type":"string"}},["number"]),
                lambda p:gh.merge_pull_request(p["number"],merge_method=p.get("merge_method","merge"))),
        ))


    ollama_url=os.environ.get("SOFIA_OLLAMA_URL","http://127.0.0.1:11434").strip()
    if ollama_url:
        ollama=OllamaAdapter(ollama_url)
        tools.extend((
            _tool("ollama.models","List installed Ollama models. Read-only.",_object(),lambda p:ollama.models()),
            _tool("ollama.running","Inspect currently loaded Ollama models/processes. Read-only.",_object(),lambda p:ollama.running()),
            _tool("ollama.model.show","Inspect one Ollama model's metadata. Read-only.",
                _object({"name":{"type":"string"}},["name"]),lambda p:ollama.show(p["name"])),
        ))

    discord_ids=(
        os.environ.get("SOFIA_DISCORD_OWNER_ID","").strip(),
        os.environ.get("SOFIA_DISCORD_BOT_ID","").strip(),
        os.environ.get("SOFIA_DISCORD_DM_CHANNEL_ID","").strip(),
    )
    if all(discord_ids):
        from sofia.discord.provisioning import DiscordIdentity
        identity=DiscordIdentity(int(discord_ids[0]),int(discord_ids[1]),int(discord_ids[2]))
        discord=DiscordOperatorAdapter(state_path,identity)
        tools.extend((
            _tool("discord.status","Inspect durable Discord channel/binding/delivery status. Read-only.",_object(),lambda p:discord.status()),
            _tool("discord.pause","Pause the configured Discord binding.",_object(),lambda p:discord.control("pause")),
            _tool("discord.resume","Resume the configured Discord binding.",_object(),lambda p:discord.control("resume")),
            _tool("discord.revoke","Revoke the configured Discord binding.",_object(),lambda p:discord.control("revoke")),
        ))


    if platform.system() in ("Windows","Linux"):
        local_maintenance=LocalMaintenanceAdapter()
        tools.extend((
            _tool("local.service.start","Start one exact local operating-system service.",
                _object({"name":{"type":"string"}},["name"]),
                lambda p:local_maintenance.service(p["name"],"start")),
            _tool("local.service.stop","Stop one exact local operating-system service.",
                _object({"name":{"type":"string"}},["name"]),
                lambda p:local_maintenance.service(p["name"],"stop")),
            _tool("local.service.restart","Restart one exact local operating-system service.",
                _object({"name":{"type":"string"}},["name"]),
                lambda p:local_maintenance.service(p["name"],"restart")),
            _tool("local.host.reboot","Reboot the current host using the platform's fixed reboot operation.",
                _object(),lambda p:local_maintenance.reboot()),
            _tool("local.package.update","Update one exact local package using the platform package manager.",
                _object({"package":{"type":"string"}},["package"]),
                lambda p:local_maintenance.package_update(p["package"])),
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
    tools.extend((
        _tool("storage.roots","List configured storage/NAS roots by index. Read-only.",_object(),lambda p:storage.roots_info()),
        _tool("storage.usage","Inspect disk usage for configured storage/NAS roots. Read-only.",_object(),lambda p:storage.usage()),
        _tool("storage.list","List one directory inside a configured storage/NAS root. Read-only.",
            _object({"root_index":{"type":"integer"},"path":{"type":"string"}},["root_index"]),
            lambda p:storage.list(p["root_index"],p.get("path","."))),
        _tool("storage.read_text","Read one bounded UTF-8 file inside a configured storage/NAS root. Read-only.",
            _object({"root_index":{"type":"integer"},"path":{"type":"string"},"max_bytes":{"type":"integer"}},["root_index","path"]),
            lambda p:storage.read_text(p["root_index"],p["path"],max_bytes=p.get("max_bytes",1024*1024))),
        _tool("storage.write_text","Write one bounded text file inside a configured storage/NAS root.",
            _object({"root_index":{"type":"integer"},"path":{"type":"string"},"content":{"type":"string"},"overwrite":{"type":"boolean"}},["root_index","path","content"]),
            lambda p:storage.write_text(p["root_index"],p["path"],p["content"],overwrite=bool(p.get("overwrite",False)))),
        _tool("storage.mkdir","Create one directory inside a configured storage/NAS root.",
            _object({"root_index":{"type":"integer"},"path":{"type":"string"}},["root_index","path"]),
            lambda p:storage.mkdir(p["root_index"],p["path"])),
        _tool("storage.copy","Copy one file inside the same configured storage/NAS root.",
            _object({"root_index":{"type":"integer"},"source":{"type":"string"},"destination":{"type":"string"},"overwrite":{"type":"boolean"}},["root_index","source","destination"]),
            lambda p:storage.copy(p["root_index"],p["source"],p["destination"],overwrite=bool(p.get("overwrite",False)))),
        _tool("storage.move","Move one path inside the same configured storage/NAS root.",
            _object({"root_index":{"type":"integer"},"source":{"type":"string"},"destination":{"type":"string"},"overwrite":{"type":"boolean"}},["root_index","source","destination"]),
            lambda p:storage.move(p["root_index"],p["source"],p["destination"],overwrite=bool(p.get("overwrite",False)))),
        _tool("storage.delete","Delete one path inside a configured storage/NAS root.",
            _object({"root_index":{"type":"integer"},"path":{"type":"string"},"recursive":{"type":"boolean"}},["root_index","path"]),
            lambda p:storage.delete(p["root_index"],p["path"],recursive=bool(p.get("recursive",False)))),
    ))

    if state_path.exists():
        sqlite=SQLiteReadAdapter(state_path)
        tools.extend((
            _tool("sqlite.state.tables","List tables in Sofía's local SQLite state database. Read-only.",_object(),lambda p:sqlite.tables()),
            _tool("sqlite.state.query","Run a bounded read-only query against Sofía's state database.",
                _object({"sql":{"type":"string"},"limit":{"type":"integer"}},["sql"]),
                lambda p:sqlite.query(p["sql"],limit=p.get("limit",200))),
            _tool("sqlite.state.integrity","Run SQLite integrity_check against Sofía's state database. Read-only.",_object(),
                lambda p:sqlite.integrity_check()),
            _tool("sqlite.state.backup","Create a consistent timestamped backup of Sofía's state database.",_object(),
                lambda p:sqlite.backup()),
            _tool("sqlite.state.wal_checkpoint","Run one explicit WAL checkpoint mode against Sofía's state database.",
                _object({"mode":{"type":"string"}}),lambda p:sqlite.wal_checkpoint(p.get("mode","PASSIVE"))),
            _tool("sqlite.state.vacuum","Run VACUUM against Sofía's state database.",_object(),lambda p:sqlite.vacuum()),
        ))

    return tuple(tools)
