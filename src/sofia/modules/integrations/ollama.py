"""Ollama local-service inspection and model-lifecycle adapter."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from time import sleep
from typing import Any
from sofia.modules.inference.endpoint import (
    configured_ollama_endpoint,
    validate_ollama_endpoint,
)
from .http import JsonHttpClient

class OllamaConnectionState(str,Enum):
    ONLINE="online"
    OFFLINE="offline"
    STARTING="starting"
    READY="ready"
    FAILED="failed"

@dataclass(frozen=True,slots=True)
class OllamaConnectionDiagnostic:
    endpoint:str
    state:OllamaConnectionState
    observed_at:datetime
    attempts:int
    last_success_at:datetime|None=None
    last_failure_at:datetime|None=None
    failure_kind:str|None=None

class OllamaAdapter:
    def __init__(self,base_url:str|None=None)->None:
        self.base_url=(
            configured_ollama_endpoint()
            if base_url is None else validate_ollama_endpoint(base_url)
        )
        self.http=JsonHttpClient(self.base_url)
        self.pull_timeout=7200.0
        self.load_timeout=600.0
        self.unload_timeout=60.0
        self.last_success_at:datetime|None=None
        self.last_failure_at:datetime|None=None
        self.last_failure_kind:str|None=None
    def models(self)->Any:
        return self.http.request("GET","/api/tags",max_bytes=1_048_576)
    def version(self)->Any:
        """Read the local Ollama service version without inference or writes."""
        return self.http.request("GET","/api/version",max_bytes=65_536)
    def running(self)->Any:
        return self.http.request("GET","/api/ps")
    def show(self,name:str)->Any:
        if not name.strip(): raise ValueError("model name required")
        return self.http.request("POST","/api/show",payload={"name":name},max_bytes=2_097_152)
    def pull(self,name:str)->Any:
        """Install or update one exact Ollama model tag."""
        if not isinstance(name,str) or not name.strip():
            raise ValueError("model name required")
        return self.http.request(
            "POST",
            "/api/pull",
            payload={"model":name,"stream":False},
            timeout=getattr(self,"pull_timeout",7200.0),
        )
    def load(self,name:str,*,keep_alive:str="10m")->Any:
        """Ask Ollama to make one exact installed model resident."""
        if not isinstance(name,str) or not name.strip(): raise ValueError("model name required")
        if not isinstance(keep_alive,str) or not keep_alive.strip():
            raise ValueError("keep_alive required")
        return self.http.request(
            "POST",
            "/api/generate",
            payload={"model":name,"keep_alive":keep_alive,"prompt":"","stream":False},
            timeout=getattr(self,"load_timeout",600.0),
        )
    def unload(self,name:str)->Any:
        """Ask Ollama to unload one exact model without stopping the service."""
        if not isinstance(name,str) or not name.strip(): raise ValueError("model name required")
        return self.http.request(
            "POST",
            "/api/generate",
            payload={"model":name,"keep_alive":0,"prompt":"","stream":False},
            timeout=getattr(self,"unload_timeout",60.0),
        )

    def diagnose(
        self, *, service_state:str|None=None, attempts:int=2,
        retry_delay_seconds:float=0.05,
    )->OllamaConnectionDiagnostic:
        """Probe availability without loading, installing or switching a model."""
        if type(attempts) is not int or not 1<=attempts<=3:
            raise ValueError("diagnostic attempts must be in 1..3")
        if type(retry_delay_seconds) not in {int,float} or not 0<=retry_delay_seconds<=1:
            raise ValueError("diagnostic retry delay must be in 0..1 seconds")
        if service_state not in {None,"running","starting","stopped","failed","unknown"}:
            raise ValueError("unsupported service state")
        if service_state=="starting":
            now=datetime.now(timezone.utc)
            return OllamaConnectionDiagnostic(
                self.base_url,OllamaConnectionState.STARTING,now,0,
                self.last_success_at,self.last_failure_at,self.last_failure_kind,
            )
        failure:Exception|None=None
        connected=False
        used=0
        for used in range(1,attempts+1):
            try:
                self.version()
                connected=True
                self.last_success_at=datetime.now(timezone.utc)
                self.models()
                now=datetime.now(timezone.utc)
                self.last_success_at=now
                self.last_failure_kind=None
                return OllamaConnectionDiagnostic(
                    self.base_url,OllamaConnectionState.READY,now,used,
                    self.last_success_at,self.last_failure_at,None,
                )
            except Exception as exc:
                failure=exc
                if used<attempts and retry_delay_seconds:
                    sleep(retry_delay_seconds)
        now=datetime.now(timezone.utc)
        self.last_failure_at=now
        self.last_failure_kind=type(failure).__name__ if failure is not None else "UnknownError"
        state=(
            OllamaConnectionState.ONLINE if connected else
            OllamaConnectionState.FAILED if service_state=="failed" else
            OllamaConnectionState.OFFLINE
        )
        return OllamaConnectionDiagnostic(
            self.base_url,state,now,used,self.last_success_at,
            self.last_failure_at,self.last_failure_kind,
        )
