"""Home Assistant REST adapter."""
from __future__ import annotations
from datetime import datetime, timezone
from re import fullmatch
from typing import Mapping
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.model import ExternalObservationState,ExternalSystem,ExternalSystemAction,ExternalSystemObservation,ExternalSystemResult,ExternalSystemResultKind,ExternalSystemType
from sofia.integrate.http import JsonHttpClient,UrllibJsonHttpClient

_IDENTIFIER=r"[a-z0-9_]+"

class HomeAssistantAdapter(ExternalIntegrationAdapter):
    def __init__(self,base_url:str,token:str,*,http:JsonHttpClient|None=None,system_id:str="home-assistant")->None:
        if not base_url.strip(): raise ValueError("Home Assistant base_url is required")
        if not token.strip(): raise ValueError("Home Assistant token is required")
        self._base_url=base_url.rstrip("/"); self._token=token; self._http=http or UrllibJsonHttpClient()
        self._system=ExternalSystem(system_id,"Home Assistant",ExternalSystemType.PLATFORM,"Home automation platform")
    @property
    def name(self)->str: return "home-assistant-rest"
    @property
    def system(self)->ExternalSystem: return self._system
    @property
    def _headers(self)->dict[str,str]: return {"Authorization":f"Bearer {self._token}"}
    def observe(self)->ExternalSystemObservation:
        api=self._http.request("GET",f"{self._base_url}/api/",headers=self._headers)
        states=self._http.request("GET",f"{self._base_url}/api/states",headers=self._headers)
        entities=states.payload if isinstance(states.payload,list) else []
        return ExternalSystemObservation(self.system,datetime.now(timezone.utc),ExternalObservationState.VERIFIED,
            {"api_status":api.payload,"entity_count":len(entities),"entities":entities},self.name)
    def execute_action(self,action:ExternalSystemAction)->ExternalSystemResult:
        if action.system_id!=self.system.system_id: raise ValueError("action targets a different system")
        if action.action_name!="call_service": raise ValueError("unsupported Home Assistant action")
        domain=action.parameters.get("domain"); service=action.parameters.get("service"); data=action.parameters.get("data",{})
        if not isinstance(domain,str) or fullmatch(_IDENTIFIER,domain) is None: raise ValueError("invalid Home Assistant domain")
        if not isinstance(service,str) or fullmatch(_IDENTIFIER,service) is None: raise ValueError("invalid Home Assistant service")
        if not isinstance(data,Mapping): raise TypeError("Home Assistant service data must be a mapping")
        response=self._http.request("POST",f"{self._base_url}/api/services/{domain}/{service}",headers=self._headers,payload=dict(data))
        return ExternalSystemResult(self.system.system_id,ExternalSystemResultKind.SUCCESS,
            {"status":response.status,"response":response.payload},datetime.now(timezone.utc),self.name)
