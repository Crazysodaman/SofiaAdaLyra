"""JMRI JSON servlet adapter for roster observation."""
from __future__ import annotations
from datetime import datetime,timezone
from sofia.external.adapter import ExternalIntegrationAdapter
from sofia.external.model import ExternalObservationState,ExternalSystem,ExternalSystemObservation,ExternalSystemType
from sofia.integrate.http import JsonHttpClient,UrllibJsonHttpClient

class JmriAdapter(ExternalIntegrationAdapter):
    def __init__(self,base_url:str,*,api_version:str="v5",http:JsonHttpClient|None=None,system_id:str="jmri")->None:
        if not base_url.strip(): raise ValueError("JMRI base_url is required")
        self._base_url=base_url.rstrip("/")
        self._version=api_version
        self._http=http or UrllibJsonHttpClient()
        self._system=ExternalSystem(system_id,"JMRI",ExternalSystemType.APPLICATION,"Java Model Railroad Interface")
    @property
    def name(self)->str: return "jmri-json"
    @property
    def system(self)->ExternalSystem: return self._system
    def observe(self)->ExternalSystemObservation:
        roster=self._http.request("GET",f"{self._base_url}/json/{self._version}/roster")
        items=roster.payload if isinstance(roster.payload,list) else []
        return ExternalSystemObservation(self.system,datetime.now(timezone.utc),ExternalObservationState.VERIFIED,
            {"roster_count":len(items),"roster":items},self.name)
