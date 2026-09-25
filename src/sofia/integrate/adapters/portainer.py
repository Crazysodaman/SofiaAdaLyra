"""Portainer adapter using its Docker API reverse proxy."""
from __future__ import annotations
from datetime import datetime,timezone
from re import fullmatch
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.model import ExternalObservationState,ExternalSystem,ExternalSystemAction,ExternalSystemObservation,ExternalSystemResult,ExternalSystemResultKind,ExternalSystemType
from sofia.integrate.http import JsonHttpClient,UrllibJsonHttpClient

_CONTAINER=r"[A-Za-z0-9_.:-]+"

class PortainerAdapter(ExternalIntegrationAdapter):
    def __init__(self,base_url:str,api_key:str,*,http:JsonHttpClient|None=None,system_id:str="portainer")->None:
        if not base_url.strip(): raise ValueError("Portainer base_url is required")
        if not api_key.strip(): raise ValueError("Portainer api_key is required")
        self._base_url=base_url.rstrip("/"); self._api_key=api_key; self._http=http or UrllibJsonHttpClient()
        self._system=ExternalSystem(system_id,"Portainer",ExternalSystemType.PLATFORM,"Container management platform")
    @property
    def name(self)->str: return "portainer-api"
    @property
    def system(self)->ExternalSystem: return self._system
    @property
    def _headers(self)->dict[str,str]: return {"X-API-Key":self._api_key}
    def observe(self)->ExternalSystemObservation:
        response=self._http.request("GET",f"{self._base_url}/api/endpoints",headers=self._headers)
        endpoints=response.payload if isinstance(response.payload,list) else []
        return ExternalSystemObservation(self.system,datetime.now(timezone.utc),ExternalObservationState.VERIFIED,
            {"endpoints":endpoints,"endpoint_count":len(endpoints)},self.name)
    def _container_action(self,endpoint_id:object,container_id:object,operation:str):
        if type(endpoint_id) is not int or endpoint_id<=0: raise ValueError("endpoint_id must be positive")
        if not isinstance(container_id,str) or fullmatch(_CONTAINER,container_id) is None: raise ValueError("invalid container_id")
        return self._http.request("POST",f"{self._base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/{operation}",headers=self._headers)
    def execute_action(self,action:ExternalSystemAction)->ExternalSystemResult:
        if action.system_id!=self.system.system_id: raise ValueError("action targets a different system")
        operation={"restart_container":"restart","start_container":"start","stop_container":"stop"}.get(action.action_name)
        if operation is None: raise ValueError("unsupported Portainer action")
        response=self._container_action(action.parameters.get("endpoint_id"),action.parameters.get("container_id"),operation)
        return ExternalSystemResult(self.system.system_id,ExternalSystemResultKind.SUCCESS,
            {"status":response.status,"operation":operation},datetime.now(timezone.utc),self.name)
