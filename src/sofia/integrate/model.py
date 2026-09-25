from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

class SideEffectClass(str,Enum):
    READ_ONLY="read_only"; REVERSIBLE_WRITE="reversible_write"; DESTRUCTIVE="destructive"; EXTERNAL_COMMUNICATION="external_communication"

@dataclass(frozen=True)
class AdapterManifest:
    tool_id:str; version:str; owner:str; side_effect:SideEffectClass; required_capabilities:tuple[str,...]; input_schema:Mapping[str,Any]; output_schema:Mapping[str,Any]
    def __post_init__(self):
        if not all((self.tool_id.strip(),self.version.strip(),self.owner.strip())): raise ValueError("tool_id, version and owner required")

@dataclass(frozen=True)
class ToolInvocation:
    invocation_id:str; tool_id:str; arguments:Mapping[str,Any]; authorized:bool=False
    def __post_init__(self):
        if not self.invocation_id.strip() or not self.tool_id.strip(): raise ValueError("invocation_id and tool_id required")

@dataclass(frozen=True)
class ToolReceipt:
    invocation_id:str; tool_id:str; version:str; started_at:datetime; finished_at:datetime; succeeded:bool; output:Any=None; error:str|None=None
    def __post_init__(self):
        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None: raise ValueError("receipt timestamps must be timezone-aware")
        if self.finished_at < self.started_at: raise ValueError("finished_at precedes started_at")
