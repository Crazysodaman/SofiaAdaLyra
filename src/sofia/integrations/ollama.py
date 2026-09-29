"""Ollama local-service inspection and model-lifecycle adapter."""
from __future__ import annotations
from typing import Any
from .http import JsonHttpClient

class OllamaAdapter:
    def __init__(self,base_url:str="http://127.0.0.1:11434")->None:
        self.http=JsonHttpClient(base_url)
    def models(self)->Any:
        return self.http.request("GET","/api/tags")
    def running(self)->Any:
        return self.http.request("GET","/api/ps")
    def show(self,name:str)->Any:
        if not name.strip(): raise ValueError("model name required")
        return self.http.request("POST","/api/show",payload={"name":name})
    def load(self,name:str,*,keep_alive:str="10m")->Any:
        """Ask Ollama to make one exact installed model resident."""
        if not isinstance(name,str) or not name.strip(): raise ValueError("model name required")
        if not isinstance(keep_alive,str) or not keep_alive.strip():
            raise ValueError("keep_alive required")
        return self.http.request(
            "POST",
            "/api/generate",
            payload={"model":name,"keep_alive":keep_alive,"prompt":"","stream":False},
        )
    def unload(self,name:str)->Any:
        """Ask Ollama to unload one exact model without stopping the service."""
        if not isinstance(name,str) or not name.strip(): raise ValueError("model name required")
        return self.http.request(
            "POST",
            "/api/generate",
            payload={"model":name,"keep_alive":0,"prompt":"","stream":False},
        )
