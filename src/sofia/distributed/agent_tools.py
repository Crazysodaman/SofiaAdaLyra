"""Default typed operations exposed by the fleet agent."""
from __future__ import annotations
from dataclasses import asdict,is_dataclass
from enum import Enum
import os,platform
from pathlib import Path
from typing import Any,Mapping

from sofia.integrations.hyperv import HyperVAdapter
from sofia.integrations.local_maintenance import LocalMaintenanceAdapter
from sofia.integrations.portainer import PortainerAdapter
from sofia.machine.hardware import create_hardware_discovery
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

def create_default_agent_dispatcher()->RemoteAgentDispatcher:
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
        dispatcher.register("container.manage","restart",lambda p:_plain(
            port.restart(str(p["container"]),timeout_seconds=int(p.get("timeout_seconds",10)))
        ))

    return dispatcher
