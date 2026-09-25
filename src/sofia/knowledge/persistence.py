from __future__ import annotations
import json,os
from pathlib import Path
from datetime import datetime
from .model import KnowledgeDocument,KnowledgeFact,SourceKind
from .store import KnowledgeStore

class JsonKnowledgeStore(KnowledgeStore):
    """Atomic durable provenance store; successful mutations are persisted."""
    def __init__(self,path:Path)->None:
        super().__init__(); self.path=path; self._loading=True
        if path.exists(): self._load()
        self._loading=False
    def _load(self)->None:
        data=json.loads(self.path.read_text(encoding="utf-8"))
        for d in data.get("documents",[]):
            d["source_kind"]=SourceKind(d["source_kind"]); d["retrieved_at"]=datetime.fromisoformat(d["retrieved_at"])
            super().register_document(KnowledgeDocument(**d))
        for raw in data.get("facts",[]):
            raw["observed_at"]=datetime.fromisoformat(raw["observed_at"]); raw["supersedes"]=tuple(raw.get("supersedes",()))
            super().record_fact(KnowledgeFact(**raw))
    def register_document(self,document:KnowledgeDocument)->None:
        super().register_document(document)
        if not self._loading: self.flush()
    def record_fact(self,fact:KnowledgeFact)->None:
        super().record_fact(fact)
        if not self._loading: self.flush()
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={"documents":[dict(document_id=d.document_id,source_kind=d.source_kind.value,source_uri=d.source_uri,version=d.version,retrieved_at=d.retrieved_at.isoformat(),content_hash=d.content_hash,trusted_for_reference=d.trusted_for_reference) for d in self._documents.values()],
              "facts":[dict(fact_id=x.fact_id,document_id=x.document_id,statement=x.statement,locator=x.locator,observed_at=x.observed_at.isoformat(),supersedes=list(x.supersedes)) for x in self._facts.values()]}
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        with tmp.open("w",encoding="utf-8") as fh:
            json.dump(data,fh,sort_keys=True,indent=2); fh.flush(); os.fsync(fh.fileno())
        tmp.replace(self.path)
