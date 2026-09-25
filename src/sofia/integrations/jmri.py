"""JMRI Web Server JSON adapter.

JMRI exposes typed objects at /json/type and /json/type/name. The adapter keeps
operations typed and does not expose arbitrary URLs.
"""
from __future__ import annotations
from urllib.parse import quote
from typing import Any
from .http import JsonHttpClient

class JmriAdapter:
    ON=2; OFF=4; IDLE=8; UNKNOWN=0
    def __init__(self,base_url:str)->None:
        self.http=JsonHttpClient(base_url)
    def types(self)->Any:
        return self.http.request("GET","/json/type")
    def power(self)->Any:
        return self.http.request("GET","/json/power")
    def roster(self)->Any:
        return self.http.request("GET","/json/roster")
    def object(self,object_type:str,name:str)->Any:
        self._identifier(object_type,"object_type"); self._identifier(name,"name",allow_spaces=True)
        return self.http.request("GET",f"/json/{quote(object_type,safe='')}/{quote(name,safe='')}")
    def set_power(self,name:str,state:int,*,prefix:str|None=None)->Any:
        self._identifier(name,"name",allow_spaces=True)
        if state not in (self.ON,self.OFF,self.IDLE): raise ValueError("JMRI power state must be ON(2), OFF(4), or IDLE(8)")
        payload={"state":state}
        if prefix is not None:
            self._identifier(prefix,"prefix"); payload["prefix"]=prefix
        return self.http.request("POST",f"/json/power/{quote(name,safe='')}",payload=payload)
    @staticmethod
    def _identifier(value:str,label:str,allow_spaces:bool=False)->None:
        if not isinstance(value,str) or not value.strip(): raise ValueError(f"{label} required")
        if "/" in value or "\\" in value: raise ValueError(f"invalid {label}")
        if not allow_spaces and any(ch.isspace() for ch in value): raise ValueError(f"{label} cannot contain spaces")
