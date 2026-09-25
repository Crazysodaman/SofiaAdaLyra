from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from .model import KnowledgeDocument, KnowledgeFact, SourceKind
from .store import KnowledgeStore

class JsonKnowledgeStore(KnowledgeStore):
    """Small durable provenance store; atomic replace keeps partial writes out."""
    def __init__(self,path:Path)->None:
        super().__init__(); self.path=path
        if path.exists(): self._load()
    def _load(self)->None:
        data=json.loads(self.path.read_text(encoding="utf-8"))
        for d in data.get("documents",[]):
            d["source_kind"]=SourceKind(d["source_kind"]); d["retrieved_at"]=datetime.fromisoformat(d["retrieved_at"])
            self.register_document(KnowledgeDocument(**d))
        for f in data.get("facts",[]):
            f["observed_at"]=datetime.fromisoformat(f["observed_at"]); f["supersedes"]=tuple(f.get("supersedes",()))
            self.record_fact(KnowledgeFact(**f))
    def flush(self)->None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data={"documents":[dict(document_id=d.document_id,source_kind=d.source_kind.value,source_uri=d.source_uri,version=d.version,retrieved_at=d.retrieved_at.isoformat(),content_hash=d.content_hash,trusted_for_reference=d.trusted_for_reference) for d in self._documents.values()],
              "facts":[dict(fact_id=f.fact_id,document_id=f.document_id,statement=f.statement,locator=f.locator,observed_at=f.observed_at.isoformat(),supersedes=list(f.supersedes)) for f in self._facts.values()]}
        tmp=self.path.with_suffix(self.path.suffix+".tmp"); tmp.write_text(json.dumps(data,sort_keys=True,indent=2),encoding="utf-8"); tmp.replace(self.path)
