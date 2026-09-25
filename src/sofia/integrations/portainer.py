"""Portainer/Docker adapter using Portainer's Docker proxy."""
from __future__ import annotations
from typing import Any
from .http import JsonHttpClient

class PortainerAdapter:
    def __init__(self,base_url:str,api_key:str,endpoint_id:int)->None:
        if not api_key.strip(): raise ValueError("Portainer API key required")
        if endpoint_id<1: raise ValueError("Portainer endpoint_id must be positive")
        self.http=JsonHttpClient(base_url,headers={"X-API-Key":api_key}); self.endpoint_id=endpoint_id
    def endpoints(self)->list[dict[str,Any]]:
        data=self.http.request("GET","/api/endpoints")
        if not isinstance(data,list): raise RuntimeError("invalid Portainer endpoints response")
        return data
    def containers(self,*,all_containers:bool=True)->list[dict[str,Any]]:
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/containers/json",query={"all":"1" if all_containers else "0"})
        if not isinstance(data,list): raise RuntimeError("invalid Docker container response")
        return data
    def container(self,container_id:str)->dict[str,Any]:
        if not container_id.strip() or "/" in container_id: raise ValueError("invalid container_id")
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/containers/{container_id}/json")
        if not isinstance(data,dict): raise RuntimeError("invalid Docker inspect response")
        return data
    def restart(self,container_id:str,*,timeout_seconds:int=10)->None:
        if not container_id.strip() or "/" in container_id: raise ValueError("invalid container_id")
        if timeout_seconds<0 or timeout_seconds>300: raise ValueError("timeout_seconds out of range")
        self.http.request("POST",f"/api/endpoints/{self.endpoint_id}/docker/containers/{container_id}/restart",query={"t":timeout_seconds})
