"""Default typed operations exposed by the fleet agent."""
from __future__ import annotations
from dataclasses import asdict,is_dataclass
from enum import Enum
import os,platform
from pathlib import Path
from typing import Any,Mapping

from sofia.integrations.hyperv import HyperVAdapter
from sofia.integrations.local_maintenance import LocalMaintenanceAdapter
from sofia.integrations.ollama import OllamaAdapter
from sofia.integrations.portainer import PortainerAdapter
from sofia.machine.hardware import create_hardware_discovery
from sofia.ops.local_telemetry import collect_local_telemetry
from sofia.distributed.release_agent import create_agent_release_service_from_environment
from sofia.system.capability import create_local_system_backend
from sofia.system.model import SystemCapabilityName,SystemCapabilityRequest

from .agent import RemoteAgentDispatcher

def _plain(value:Any)->Any:
    if is_dataclass(value): return {k:_plain(v) for k,v in asdict(value).items()}
    if isinstance(value,Enum): return value.value
    if isinstance(value,Path): return str(value)
    if isinstance(value,Mapping): return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set,frozenset)): return [_plain(v) for v in value]
    return value

def create_default_agent_dispatcher(
    *,
    inference_models: tuple[str, ...] = (),
    release_service=None,
)->RemoteAgentDispatcher:
    dispatcher=RemoteAgentDispatcher()
    backend=create_local_system_backend()
    by_name={cap.name:cap for cap in backend.supported_capabilities}

    def system_handler(name:SystemCapabilityName):
        capability=by_name[name]
        def execute(parameters):
            result=backend.execute(SystemCapabilityRequest(capability,dict(parameters)))
            return _plain(result)
        return execute

    if SystemCapabilityName.PROCESS_INSPECT in by_name:
        dispatcher.register("system.inspect","process",system_handler(SystemCapabilityName.PROCESS_INSPECT))
    if SystemCapabilityName.SYSTEM_INSPECT in by_name:
        dispatcher.register("system.inspect","system",system_handler(SystemCapabilityName.SYSTEM_INSPECT))
    if SystemCapabilityName.NETWORK_INSPECT in by_name:
        dispatcher.register("system.inspect","network",system_handler(SystemCapabilityName.NETWORK_INSPECT))
    if SystemCapabilityName.SERVICE_INSPECT in by_name:
        dispatcher.register("system.inspect","service",system_handler(SystemCapabilityName.SERVICE_INSPECT))

    hardware=create_hardware_discovery()
    dispatcher.register("system.inspect","hardware",lambda p:_plain(hardware.discover()))
    dispatcher.register(
        "ops.telemetry",
        "latest",
        lambda p: _plain(collect_local_telemetry()),
    )

    if not isinstance(inference_models, tuple):
        raise TypeError("inference_models must be a tuple")
    if any(
        not isinstance(model, str) or not model.strip()
        for model in inference_models
    ):
        raise ValueError("inference_models must contain nonempty strings")

    ollama=OllamaAdapter()
    dispatcher.register(
        "llm.inspect",
        "inference_policy",
        lambda p: {"allowed_models": list(inference_models)},
    )
    dispatcher.register("llm.inspect","models",lambda p:_plain(ollama.models()))
    dispatcher.register("llm.inspect","running",lambda p:_plain(ollama.running()))
    dispatcher.register(
        "llm.inspect",
        "show",
        lambda p:_plain(ollama.show(str(p["model"]))),
    )
    dispatcher.register(
        "llm.manage",
        "pull",
        lambda p:_plain(ollama.pull(str(p["model"]))),
    )
    dispatcher.register(
        "llm.manage",
        "load",
        lambda p:_plain(
            ollama.load(
                str(p["model"]),
                keep_alive=str(p.get("keep_alive","10m")),
            )
        ),
    )
    dispatcher.register(
        "llm.manage",
        "unload",
        lambda p:_plain(ollama.unload(str(p["model"]))),
    )

    maintenance=LocalMaintenanceAdapter()
    dispatcher.register("service.manage","start",lambda p:_plain(maintenance.service(str(p["service"]),"start")))
    dispatcher.register("service.manage","stop",lambda p:_plain(maintenance.service(str(p["service"]),"stop")))
    dispatcher.register("service.manage","restart",lambda p:_plain(maintenance.service(str(p["service"]),"restart")))
    dispatcher.register("system.manage","reboot",lambda p:_plain(maintenance.reboot()))
    dispatcher.register("package.manage","update",lambda p:_plain(maintenance.package_update(str(p["package"]))))

    if platform.system()=="Windows":
        hyperv=HyperVAdapter()
        dispatcher.register("vm.inspect","list",lambda p:_plain(hyperv.vms()))
        dispatcher.register("vm.inspect","get",lambda p:_plain(hyperv.vm(str(p["vm"]))))
        dispatcher.register("vm.manage","start",lambda p:_plain(hyperv.start(str(p["vm"]))))
        dispatcher.register("vm.manage","stop",lambda p:_plain(hyperv.stop(str(p["vm"]),force=bool(p.get("force",False)))))

    port_url=os.environ.get("SOFIA_AGENT_PORTAINER_URL","").strip()
    port_key=os.environ.get("SOFIA_AGENT_PORTAINER_API_KEY","").strip()
    port_endpoint=os.environ.get("SOFIA_AGENT_PORTAINER_ENDPOINT_ID","").strip()
    if port_url and port_key and port_endpoint:
        port=PortainerAdapter(port_url,port_key,int(port_endpoint))
        dispatcher.register("container.inspect","list",lambda p:_plain(port.containers()))
        dispatcher.register("container.inspect","get",lambda p:_plain(port.container(str(p["container"]))))
        dispatcher.register("container.inspect","stats",lambda p:_plain(port.container_stats(str(p["container"]))))
        dispatcher.register("container.inspect","logs",lambda p:_plain(port.container_logs(
            str(p["container"]),
            tail=int(p.get("tail",200)),
            max_bytes=int(p.get("max_bytes",262144)),
        )))
        dispatcher.register("container.inspect","info",lambda p:_plain(port.info()))
        dispatcher.register("container.inspect","summary",lambda p:_plain(port.summary()))
        dispatcher.register("container.inspect","images",lambda p:_plain(port.images()))
        dispatcher.register("container.inspect","volumes",lambda p:_plain(port.volumes()))
        dispatcher.register("container.inspect","networks",lambda p:_plain(port.networks()))
        dispatcher.register("container.inspect","stacks",lambda p:_plain(port.stacks()))
        dispatcher.register("container.manage","restart",lambda p:_plain(
            port.restart(str(p["container"]),timeout_seconds=int(p.get("timeout_seconds",10)))
        ))

    if release_service is None:
        release_service=create_agent_release_service_from_environment()
    if release_service is not None:
        dispatcher.register(
            "release.inspect",
            "current",
            lambda p:_plain(release_service.current(dict(p))),
        )
        dispatcher.register(
            "release.manage",
            "stage",
            lambda p:_plain(release_service.stage(dict(p))),
        )
        dispatcher.register(
            "release.manage",
            "activate",
            lambda p:_plain(release_service.activate(dict(p))),
        )
        dispatcher.register(
            "release.manage",
            "rollback",
            lambda p:_plain(release_service.rollback(dict(p))),
        )

    return dispatcher
