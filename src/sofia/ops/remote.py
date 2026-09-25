"""Map typed OPS maintenance onto the existing exact-scope distributed operation contract."""
from __future__ import annotations
from uuid import UUID
from sofia.distributed.operations import RemoteOperationRequest
from .maintenance import MaintenanceOperation,MaintenanceRequest

_MAPPING={
    MaintenanceOperation.SERVICE_RESTART:("service.manage","restart"),
    MaintenanceOperation.HOST_REBOOT:("system.manage","reboot"),
    MaintenanceOperation.PACKAGE_UPDATE:("package.manage","update"),
    MaintenanceOperation.DRAIN:("workload.manage","drain"),
}

def to_remote_operation(request:MaintenanceRequest,*,remote_request_id:UUID,node_id:UUID,grant_id:UUID)->RemoteOperationRequest:
    capability,operation=_MAPPING[request.operation]
    parameters={}
    if request.operation is MaintenanceOperation.SERVICE_RESTART: parameters["service"]=request.target
    if request.operation is MaintenanceOperation.PACKAGE_UPDATE: parameters["package"]=request.target
    return RemoteOperationRequest(remote_request_id,node_id,grant_id,capability,operation,parameters)
