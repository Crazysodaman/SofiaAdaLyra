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
    def container_logs(
        self,
        container_id:str,
        *,
        tail:int=200,
        max_bytes:int=262144,
    )->str:
        if not container_id.strip() or "/" in container_id:
            raise ValueError("invalid container_id")
        if type(tail) is not int or not 1 <= tail <= 5000:
            raise ValueError("tail must be in 1..5000")
        return self.http.request_text(
            "GET",
            f"/api/endpoints/{self.endpoint_id}/docker/containers/{container_id}/logs",
            query={
                "stdout":"true",
                "stderr":"true",
                "timestamps":"true",
                "tail":str(tail),
            },
            max_bytes=max_bytes,
        )

    def container_stats(self,container_id:str)->dict[str,Any]:
        if not container_id.strip() or "/" in container_id: raise ValueError("invalid container_id")
        data=self.http.request(
            "GET",
            f"/api/endpoints/{self.endpoint_id}/docker/containers/{container_id}/stats",
            query={"stream":"false"},
        )
        if not isinstance(data,dict): raise RuntimeError("invalid Docker stats response")
        return data
    def info(self)->dict[str,Any]:
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/info")
        if not isinstance(data,dict): raise RuntimeError("invalid Docker info response")
        return data
    def images(self)->list[dict[str,Any]]:
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/images/json")
        if not isinstance(data,list): raise RuntimeError("invalid Docker images response")
        return data
    def volumes(self)->dict[str,Any]:
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/volumes")
        if not isinstance(data,dict): raise RuntimeError("invalid Docker volumes response")
        return data
    def networks(self)->list[dict[str,Any]]:
        data=self.http.request("GET",f"/api/endpoints/{self.endpoint_id}/docker/networks")
        if not isinstance(data,list): raise RuntimeError("invalid Docker networks response")
        return data
    def stacks(self)->list[dict[str,Any]]:
        data=self.http.request(
            "GET",
            "/api/stacks",
            query={"endpointId":self.endpoint_id},
        )
        if not isinstance(data,list): raise RuntimeError("invalid Portainer stacks response")
        return data
    def summary(self)->dict[str,Any]:
        info=self.info()
        containers=self.containers(all_containers=True)
        running=[]
        stopped=[]
        unhealthy=[]
        for item in containers:
            names=item.get("Names") or ()
            name=(
                str(names[0]).lstrip("/")
                if isinstance(names,list) and names
                else str(item.get("Id",""))[:12]
            )
            state=str(item.get("State","")).casefold()
            status=str(item.get("Status",""))
            if state=="running":
                running.append(name)
            else:
                stopped.append(name)
            if "unhealthy" in status.casefold():
                unhealthy.append(name)
        return {
            "endpoint_id":self.endpoint_id,
            "engine": {
                "containers":info.get("Containers"),
                "containers_running":info.get("ContainersRunning"),
                "containers_stopped":info.get("ContainersStopped"),
                "images":info.get("Images"),
                "server_version":info.get("ServerVersion"),
                "operating_system":info.get("OperatingSystem"),
                "architecture":info.get("Architecture"),
            },
            "observed_container_count":len(containers),
            "running":tuple(sorted(running)),
            "stopped":tuple(sorted(stopped)),
            "unhealthy":tuple(sorted(unhealthy)),
        }
    def restart(self,container_id:str,*,timeout_seconds:int=10)->None:
        if not container_id.strip() or "/" in container_id: raise ValueError("invalid container_id")
        if timeout_seconds<0 or timeout_seconds>300: raise ValueError("timeout_seconds out of range")
        self.http.request("POST",f"/api/endpoints/{self.endpoint_id}/docker/containers/{container_id}/restart",query={"t":timeout_seconds})
