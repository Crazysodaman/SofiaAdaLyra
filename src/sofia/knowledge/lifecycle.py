"""Durable document freshness/invalidation state separate from source content."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

class DocumentDisposition(str,Enum):
    ACTIVE="active"; SUPERSEDED="superseded"; INVALID="invalid"

@dataclass(frozen=True)
class DocumentStatus:
    document_id:str
    disposition:DocumentDisposition=DocumentDisposition.ACTIVE
    replaced_by:str|None=None

class KnowledgeLifecycle:
    def __init__(self,path:Path|None=None)->None:
        self.path=path; self._status:dict[str,DocumentStatus]={}
        if path is not None and path.exists(): self._load()
    def register(self,document_id:str)->DocumentStatus:
        if not document_id.strip(): raise ValueError("document_id required")
        existing=self._status.get(document_id)
        if existing is not None: return existing
        s=DocumentStatus(document_id); self._status[document_id]=s; self.flush(); return s
    def supersede(self,old_id:str,new_id:str)->None:
        if old_id==new_id: raise ValueError("replacement must be a different document")
        self.register(old_id); self.register(new_id)
        self._status[old_id]=DocumentStatus(old_id,DocumentDisposition.SUPERSEDED,new_id); self.flush()
    def invalidate(self,document_id:str)->None:
        self.register(document_id); self._status[document_id]=DocumentStatus(document_id,DocumentDisposition.INVALID,None); self.flush()
    def status(self,document_id:str)->DocumentStatus|None: return self._status.get(document_id)
    def active(self,document_id:str)->bool:
        s=self._status.get(document_id); return s is None or s.disposition is DocumentDisposition.ACTIVE
    def flush(self)->None:
        if self.path is None: return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        payload=[{"document_id":s.document_id,"disposition":s.disposition.value,"replaced_by":s.replaced_by} for s in self._status.values()]
        tmp=self.path.with_suffix(self.path.suffix+".tmp"); tmp.write_text(json.dumps(payload,sort_keys=True,indent=2),encoding="utf-8"); tmp.replace(self.path)
    def _load(self)->None:
        for raw in json.loads(self.path.read_text(encoding="utf-8")):
            s=DocumentStatus(raw["document_id"],DocumentDisposition(raw["disposition"]),raw.get("replaced_by")); self._status[s.document_id]=s
