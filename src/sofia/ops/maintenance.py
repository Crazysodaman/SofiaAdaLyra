"""Typed fleet maintenance requests. No arbitrary shell or argv surface exists here."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from .fleet import FleetRegistry
from .model import HostLifecycle

class MaintenanceOperation(str,Enum):
    SERVICE_RESTART="service_restart"; HOST_REBOOT="host_reboot"; PACKAGE_UPDATE="package_update"; DRAIN="drain"; CONTAINER_RESTART="container_restart"; VM_START="vm_start"; VM_STOP="vm_stop"

@dataclass(frozen=True)
class MaintenanceRequest:
    request_id:str; host_id:str; operation:MaintenanceOperation; target:str|None=None; authorized:bool=False
    def __post_init__(self):
        if not self.request_id.strip() or not self.host_id.strip(): raise ValueError("maintenance request identity required")
        if self.target is not None and not self.target.strip(): raise ValueError("maintenance target cannot be blank")

class MaintenancePolicy:
    def __init__(self,registry:FleetRegistry,*,no_reboot_hosts:frozenset[str]=frozenset())->None:
        self.registry=registry; self.no_reboot_hosts=no_reboot_hosts
    def require(self,request:MaintenanceRequest)->None:
        if not request.authorized: raise PermissionError("maintenance action requires independent authorization")
        host=self.registry.host(request.host_id)
        if host is None or not host.trusted: raise PermissionError("maintenance target is not a trusted fleet host")
        if host.lifecycle in (HostLifecycle.CANDIDATE,HostLifecycle.QUARANTINED,HostLifecycle.DECOMMISSIONED):
            raise PermissionError("host lifecycle does not permit maintenance execution")
        if request.operation is MaintenanceOperation.HOST_REBOOT and request.host_id in self.no_reboot_hosts:
            raise PermissionError("operator no-reboot pin blocks this host")
        if request.operation is MaintenanceOperation.SERVICE_RESTART and request.target is None:
            raise ValueError("service_restart requires an exact service target")
        if request.operation is MaintenanceOperation.PACKAGE_UPDATE and request.target is None:
            raise ValueError("package_update requires an exact package target")
        if request.operation in (MaintenanceOperation.CONTAINER_RESTART,MaintenanceOperation.VM_START,MaintenanceOperation.VM_STOP) and request.target is None:
            raise ValueError(f"{request.operation.value} requires an exact target")
