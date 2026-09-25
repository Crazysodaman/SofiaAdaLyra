"""Operational KNOW service: bounded ingestion, retrieval and document authoring."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from .lifecycle import KnowledgeLifecycle
from .model import KnowledgeDocument,KnowledgeFact,SourceKind
from .persistence import JsonKnowledgeStore
from .retrieval import KnowledgeRetriever

class KnowledgeServiceError(RuntimeError): pass

class KnowledgeService:
    def __init__(self,root:Path,store:JsonKnowledgeStore,lifecycle:KnowledgeLifecycle)->None:
        self.root=root.resolve(); self.store=store; self.lifecycle=lifecycle
    def _path(self,relative_path:str)->Path:
        if not isinstance(relative_path,str) or not relative_path.strip(): raise ValueError("relative_path required")
        candidate=(self.root/relative_path).resolve()
        try: candidate.relative_to(self.root)
        except ValueError as exc: raise PermissionError("knowledge path escapes authorized root") from exc
        return candidate
    @staticmethod
    def _document_id(path:Path,digest:str)->str:
        key=sha256((path.as_posix()+"\0"+digest).encode("utf-8")).hexdigest()[:20]
        return f"doc-{key}"
    def _record_text(self,path:Path,text:str,raw:bytes,source_kind:SourceKind,version:str,*,page:int|None=None)->KnowledgeDocument:
        digest=sha256(raw).hexdigest(); document_id=self._document_id(path,digest)
        doc=KnowledgeDocument(document_id,source_kind,path.as_uri(),version,datetime.now(timezone.utc),digest,True)
        self.store.register_document(doc); self.lifecycle.register(document_id)
        lines=text.splitlines()
        chunks=[]; start=1
        for index in range(0,len(lines),40):
            block=lines[index:index+40]
            statement="\n".join(block).strip()
            if not statement: continue
            end=index+len(block)
            locator=(f"page {page}, lines {start}-{end}" if page is not None else f"lines {start}-{end}")
            fact_id=f"{document_id}:{page or 0}:{index//40+1}"
            chunks.append(KnowledgeFact(fact_id,document_id,statement,locator,datetime.now(timezone.utc)))
            start=end+1
        if not chunks and text.strip():
            chunks=[KnowledgeFact(f"{document_id}:{page or 0}:1",document_id,text.strip(),f"page {page}" if page else "document",datetime.now(timezone.utc))]
        for fact in chunks: self.store.record_fact(fact)
        return doc
    def ingest_text(self,relative_path:str,*,version:str="local")->dict[str,Any]:
        path=self._path(relative_path)
        if not path.is_file(): raise KnowledgeServiceError("knowledge source must be a file")
        raw=path.read_bytes()
        try: text=raw.decode("utf-8")
        except UnicodeDecodeError as exc: raise KnowledgeServiceError("text source must be UTF-8") from exc
        kind=SourceKind.REPOSITORY if (self.root/".git").exists() else SourceKind.PROJECT_FILE
        doc=self._record_text(path,text,raw,kind,version)
        return {"document_id":doc.document_id,"source_uri":doc.source_uri,"version":doc.version,"facts":len(self.store.facts_for(doc.document_id))}
    def ingest_pdf(self,relative_path:str,*,version:str="local")->dict[str,Any]:
        path=self._path(relative_path)
        if path.suffix.lower()!=".pdf" or not path.is_file(): raise KnowledgeServiceError("PDF source must be an existing .pdf file")
        try:
            from pypdf import PdfReader
        except ImportError as exc: raise KnowledgeServiceError("PDF ingestion requires pypdf") from exc
        raw=path.read_bytes(); digest=sha256(raw).hexdigest(); document_id=self._document_id(path,digest)
        doc=KnowledgeDocument(document_id,SourceKind.MANUAL,path.as_uri(),version,datetime.now(timezone.utc),digest,True)
        self.store.register_document(doc); self.lifecycle.register(document_id)
        reader=PdfReader(str(path)); fact_count=0
        for page_number,page in enumerate(reader.pages,start=1):
            text=(page.extract_text() or "").strip()
            if not text: continue
            lines=text.splitlines()
            for index in range(0,len(lines),40):
                statement="\n".join(lines[index:index+40]).strip()
                if not statement: continue
                fact=KnowledgeFact(f"{document_id}:p{page_number}:{index//40+1}",document_id,statement,
                    f"page {page_number}, lines {index+1}-{index+len(lines[index:index+40])}",datetime.now(timezone.utc))
                self.store.record_fact(fact); fact_count+=1
        return {"document_id":doc.document_id,"source_uri":doc.source_uri,"version":doc.version,"facts":fact_count,"pages":len(reader.pages)}
    def search(self,query:str,*,limit:int=10)->tuple[dict[str,Any],...]:
        hits=KnowledgeRetriever(self.store,self.lifecycle).search(query,limit=limit)
        return tuple({"fact_id":h.fact.fact_id,"document_id":h.fact.document_id,"statement":h.fact.statement,
            "locator":h.fact.locator,"source_uri":h.source_uri,"source_version":h.source_version,"score":h.score} for h in hits)
    def document(self,document_id:str)->dict[str,Any]|None:
        doc=self.store.document(document_id)
        if doc is None: return None
        return {"document_id":doc.document_id,"source_kind":doc.source_kind.value,"source_uri":doc.source_uri,
            "version":doc.version,"retrieved_at":doc.retrieved_at.isoformat(),"content_hash":doc.content_hash,
            "active":self.lifecycle.active(document_id),
            "facts":tuple({"fact_id":f.fact_id,"statement":f.statement,"locator":f.locator} for f in self.store.facts_for(document_id))}
    def write_document(self,relative_path:str,content:str,*,overwrite:bool=False)->dict[str,Any]:
        path=self._path(relative_path)
        if not isinstance(content,str): raise TypeError("content must be text")
        if path.exists() and not overwrite: raise FileExistsError("document already exists; explicit overwrite required")
        path.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=path.parent,prefix=path.name+".",suffix=".tmp") as fh:
            fh.write(content); tmp=Path(fh.name)
        tmp.replace(path)
        return {"path":str(path.relative_to(self.root)),"bytes":len(content.encode("utf-8")),"overwritten":overwrite}
