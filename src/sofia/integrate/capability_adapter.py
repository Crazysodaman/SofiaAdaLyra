"""Typed INTEGRATE adapter over Sofía's existing CapabilitySystem."""
from __future__ import annotations
from dataclasses import asdict,is_dataclass
from typing import Any,Mapping
from sofia.capability import CapabilityRequest,CapabilitySystem
from .model import AdapterManifest,SideEffectClass

def _plain(value:Any)->Any:
    if is_dataclass(value): return {k:_plain(v) for k,v in asdict(value).items()}
    if isinstance(value,Mapping): return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [_plain(v) for v in value]
    if hasattr(value,"value"): return value.value
    return value

class CapabilitySystemAdapter:
    def __init__(self,system:CapabilitySystem,*,tool_id:str,capability_name:str,version:str="1",
                 side_effect:SideEffectClass=SideEffectClass.READ_ONLY,input_schema:Mapping[str,Any]|None=None,
                 requested_scope:Any=None)->None:
        self.system=system; self.capability_name=capability_name; self.requested_scope=requested_scope
        self.manifest=AdapterManifest(tool_id,version,"sofia.capability",side_effect,(capability_name,),
            input_schema or {"type":"object"},
            {"type":"object","required":["kind","capability"],"properties":{"kind":{},"capability":{},"evidence":{},"error":{}}})
    def invoke(self,arguments:dict[str,Any])->Any:
        capability=self.system.resolve(self.capability_name)
        request=CapabilityRequest(capability,dict(arguments),self.requested_scope,
            f"typed adapter invocation: {self.manifest.tool_id}")
        result=self.system.execute(request)
        return {"capability":result.capability,"kind":result.kind.value,"evidence":_plain(result.evidence),"error":result.error}
