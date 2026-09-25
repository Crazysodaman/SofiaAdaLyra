"""Home Assistant REST adapter."""
from __future__ import annotations
from typing import Any
from .http import JsonHttpClient

class HomeAssistantAdapter:
    def __init__(self,base_url:str,token:str)->None:
        if not token.strip(): raise ValueError("Home Assistant token required")
        self.http=JsonHttpClient(base_url,headers={"Authorization":f"Bearer {token}"})
    def health(self)->dict[str,Any]:
        data=self.http.request("GET","/api/")
        return {"reachable":True,"response":data}
    def states(self)->list[dict[str,Any]]:
        data=self.http.request("GET","/api/states")
        if not isinstance(data,list): raise RuntimeError("invalid Home Assistant states response")
        return data
    def state(self,entity_id:str)->dict[str,Any]:
        if not entity_id.strip(): raise ValueError("entity_id required")
        data=self.http.request("GET",f"/api/states/{entity_id}")
        if not isinstance(data,dict): raise RuntimeError("invalid Home Assistant state response")
        return data
    def call_service(self,domain:str,service:str,service_data:dict[str,Any]|None=None)->Any:
        for value,name in ((domain,"domain"),(service,"service")):
            if not value.strip() or "/" in value: raise ValueError(f"invalid {name}")
        return self.http.request("POST",f"/api/services/{domain}/{service}",payload=service_data or {})
