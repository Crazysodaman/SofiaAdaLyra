"""Ollama local-service inspection adapter."""
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
