"""Durable exact-version activation state for governed adapters."""
from __future__ import annotations
import json,os
from pathlib import Path

class AdapterActivationStore:
    def __init__(self,path:Path|None=None)->None:
        self.path=path; self._enabled:dict[str,str]={}
        if path is not None and path.exists():
            raw=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw,dict): raise ValueError("adapter activation state must be an object")
            self._enabled={str(k):str(v) for k,v in raw.items()}
    def version(self,tool_id:str)->str|None: return self._enabled.get(tool_id)
    def enable(self,tool_id:str,version:str)->None:
        if not tool_id.strip() or not version.strip(): raise ValueError("tool_id and version required")
        self._enabled[tool_id]=version; self.flush()
    def disable(self,tool_id:str)->None:
        self._enabled.pop(tool_id,None); self.flush()
    def flush(self)->None:
        if self.path is None: return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        with tmp.open("w",encoding="utf-8") as fh:
            json.dump(self._enabled,fh,sort_keys=True,indent=2); fh.flush(); os.fsync(fh.fileno())
        tmp.replace(self.path)
