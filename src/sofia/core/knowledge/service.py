"""Operational KNOW service: bounded ingestion, retrieval and document authoring."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any

from .access import KnowledgeAccess, KnowledgeAccessStore, KnowledgeVisibility
from .lifecycle import SQLiteKnowledgeLifecycle
from .model import KnowledgeDocument,KnowledgeFact,SourceKind
from .persistence import SQLiteKnowledgeStore
from .retrieval import KnowledgeRetriever
from .index import KnowledgeIndex, KnowledgeSection

class KnowledgeServiceError(RuntimeError): pass

class KnowledgeService:
    def __init__(
        self,
        root:Path,
        store:SQLiteKnowledgeStore,
        lifecycle:SQLiteKnowledgeLifecycle,
        access:KnowledgeAccessStore|None=None,
        index:KnowledgeIndex|None=None,
    )->None:
        self.root=root.resolve(); self.store=store; self.lifecycle=lifecycle
        self._legacy_shared_access = access is None
        if access is None:
            access=KnowledgeAccessStore(store.path)
        if not isinstance(access,KnowledgeAccessStore):
            raise TypeError("access must be KnowledgeAccessStore")
        self.access=access
        self.index=index or KnowledgeIndex(store.path)
    def _classify_private(
        self,
        document_id:str,
        *,
        principal_id:str|None,
        audience_id:str|None,
    )->None:
        if self.access.get(document_id) is not None:
            return
        if principal_id is None or audience_id is None:
            if self._legacy_shared_access:
                self.access.set(KnowledgeAccess(
                    document_id,
                    KnowledgeVisibility.SHARED,
                ))
            return
        self.access.set(KnowledgeAccess(
            document_id,
            KnowledgeVisibility.PRIVATE,
            principal_id=principal_id,
            audience_id=audience_id,
        ))

    def _path(self,relative_path:str)->Path:
        if not isinstance(relative_path,str) or not relative_path.strip(): raise ValueError("relative_path required")
        candidate=(self.root/relative_path).resolve()
        try: candidate.relative_to(self.root)
        except ValueError as exc: raise PermissionError("knowledge path escapes authorized root") from exc
        return candidate
    @staticmethod
    def _document_id(path:Path,digest:str,version:str)->str:
        if not isinstance(version,str) or not version.strip(): raise ValueError("knowledge source version required")
        key=sha256((path.as_posix()+"\0"+version+"\0"+digest).encode("utf-8")).hexdigest()[:20]
        return f"doc-{key}"
    def _record_text(
        self,path:Path,text:str,raw:bytes,source_kind:SourceKind,version:str,*,
        page:int|None=None,
        principal_id:str|None=None,
        audience_id:str|None=None,
    )->KnowledgeDocument:
        digest=sha256(raw).hexdigest(); document_id=self._document_id(path,digest,version)
        existing=self.store.document(document_id)
        if existing is not None:
            if not self.index.has_document(document_id):
                self.index.index(self._sections(
                    document_id=document_id, text=text, page=page,
                ))
            return existing
        doc=KnowledgeDocument(document_id,source_kind,path.as_uri(),version,datetime.now(timezone.utc),digest,True)
        self.store.register_document(doc); self.lifecycle.register(document_id)
        self._classify_private(
            document_id,
            principal_id=principal_id,
            audience_id=audience_id,
        )
        self._supersede_prior_revisions(doc)
        sections=self._sections(document_id=document_id,text=text,page=page)
        self.index.index(sections)
        for section in sections:
            self.store.record_fact(KnowledgeFact(
                f"{section.section_id}:fact", document_id, section.content,
                section.locator, datetime.now(timezone.utc),
            ))
        return doc

    @staticmethod
    def _sections(
        *, document_id:str, text:str, page:int|None=None,
    )->tuple[KnowledgeSection,...]:
        lines=text.splitlines()
        result=[]; heading=None; block=[]; start=1; ordinal=1
        def flush(end:int)->None:
            nonlocal block,start,ordinal
            content="\n".join(block).strip()
            if content:
                locator=(
                    f"page {page}, lines {start}-{end}"
                    if page is not None else f"lines {start}-{end}"
                )
                result.append(KnowledgeIndex.make_section(
                    document_id=document_id,ordinal=ordinal,heading=heading,
                    content=content,locator=locator,
                    metadata={"page":page,"line_start":start,"line_end":end},
                ))
                ordinal+=1
            block=[]
        for line_number,line in enumerate(lines,start=1):
            match=re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$",line)
            if match:
                flush(line_number-1)
                heading=match.group(1).strip(); start=line_number+1
                continue
            if not block: start=line_number
            block.append(line)
            if len(block)>=40:
                flush(line_number); start=line_number+1
        flush(len(lines))
        if not result and text.strip():
            result.append(KnowledgeIndex.make_section(
                document_id=document_id,ordinal=1,heading=heading,
                content=text.strip(),locator=(f"page {page}" if page else "document"),
                metadata={"page":page},
            ))
        return tuple(result)

    def _supersede_prior_revisions(self, document:KnowledgeDocument)->None:
        for prior in self.store.documents():
            if (
                prior.document_id != document.document_id
                and prior.source_uri == document.source_uri
                and self.lifecycle.active(prior.document_id)
            ):
                self.lifecycle.supersede(prior.document_id,document.document_id)
    def ingest_text(
        self,relative_path:str,*,version:str="local",
        principal_id:str|None=None,audience_id:str|None=None,
    )->dict[str,Any]:
        path=self._path(relative_path)
        if not path.is_file(): raise KnowledgeServiceError("knowledge source must be a file")
        raw=path.read_bytes()
        try: text=raw.decode("utf-8")
        except UnicodeDecodeError as exc: raise KnowledgeServiceError("text source must be UTF-8") from exc
        kind=SourceKind.REPOSITORY if (self.root/".git").exists() else SourceKind.PROJECT_FILE
        doc=self._record_text(
            path,text,raw,kind,version,
            principal_id=principal_id,
            audience_id=audience_id,
        )
        return {"document_id":doc.document_id,"source_uri":doc.source_uri,"version":doc.version,"facts":len(self.store.facts_for(doc.document_id))}
    def ingest_pdf(
        self,relative_path:str,*,version:str="local",
        principal_id:str|None=None,audience_id:str|None=None,
    )->dict[str,Any]:
        path=self._path(relative_path)
        if path.suffix.lower()!=".pdf" or not path.is_file(): raise KnowledgeServiceError("PDF source must be an existing .pdf file")
        try:
            from pypdf import PdfReader
        except ImportError as exc: raise KnowledgeServiceError("PDF ingestion requires pypdf") from exc
        raw=path.read_bytes(); digest=sha256(raw).hexdigest(); document_id=self._document_id(path,digest,version)
        existing=self.store.document(document_id)
        if existing is not None and self.index.has_document(document_id):
            return {"document_id":existing.document_id,"source_uri":existing.source_uri,"version":existing.version,
                "facts":len(self.store.facts_for(existing.document_id)),"pages":None,"already_ingested":True}
        doc=(existing or KnowledgeDocument(document_id,SourceKind.MANUAL,path.as_uri(),version,datetime.now(timezone.utc),digest,True))
        self.store.register_document(doc); self.lifecycle.register(document_id)
        self._supersede_prior_revisions(doc)
        self._classify_private(
            document_id,
            principal_id=principal_id,
            audience_id=audience_id,
        )
        reader=PdfReader(str(path)); fact_count=0; sections=[]
        for page_number,page in enumerate(reader.pages,start=1):
            text=(page.extract_text() or "").strip()
            if not text: continue
            page_sections=self._sections(
                document_id=document_id,text=text,page=page_number,
            )
            for section in page_sections:
                remapped=KnowledgeIndex.make_section(
                    document_id=document_id,ordinal=len(sections)+1,
                    heading=section.heading,content=section.content,
                    locator=section.locator,metadata=section.metadata,
                )
                sections.append(remapped)
                self.store.record_fact(KnowledgeFact(
                    f"{remapped.section_id}:fact",document_id,remapped.content,
                    remapped.locator,datetime.now(timezone.utc),
                )); fact_count+=1
        self.index.index(tuple(sections))
        return {"document_id":doc.document_id,"source_uri":doc.source_uri,"version":doc.version,"facts":fact_count,"pages":len(reader.pages)}
    def search(
        self,query:str,*,limit:int=10,
        principal_id:str|None=None,audience_id:str|None=None,
    )->tuple[dict[str,Any],...]:
        eligible=frozenset(
            document.document_id for document in self.store.documents()
            if self.lifecycle.active(document.document_id)
            and self.access.permitted(
                document.document_id,principal_id=principal_id,
                audience_id=audience_id,
            )
        )
        indexed=self.index.search(
            query,limit=min(50,max(limit*5,limit)),
            eligible_document_ids=eligible,
        )
        permitted_indexed=tuple(
            h for h in indexed
            if self.lifecycle.active(h.section.document_id)
            and self.access.permitted(
                h.section.document_id,
                principal_id=principal_id,
                audience_id=audience_id,
            )
        )[:limit]
        if permitted_indexed:
            return tuple({
                "fact_id":f"{h.section.section_id}:fact",
                "section_id":h.section.section_id,
                "document_id":h.section.document_id,
                "statement":h.section.content,
                "heading":h.section.heading,
                "locator":h.section.locator,
                "source_uri":self.store.document(h.section.document_id).source_uri,
                "source_version":self.store.document(h.section.document_id).version,
                "content_hash":h.section.content_hash,
                "metadata":h.section.metadata,
                "score":round(h.score,6),
                "lexical_score":round(h.lexical_score,6),
                "semantic_score":round(h.semantic_score,6),
                "exact_match":h.exact_match,
            } for h in permitted_indexed)
        hits=KnowledgeRetriever(self.store,self.lifecycle).search(query,limit=limit)
        hits=tuple(h for h in hits if self.access.permitted(
            h.fact.document_id,principal_id=principal_id,audience_id=audience_id,
        ))
        return tuple({"fact_id":h.fact.fact_id,"document_id":h.fact.document_id,
            "statement":h.fact.statement,"locator":h.fact.locator,
            "source_uri":h.source_uri,"source_version":h.source_version,
            "score":h.score} for h in hits)
    def document(
        self,document_id:str,*,
        principal_id:str|None=None,audience_id:str|None=None,
    )->dict[str,Any]|None:
        doc=self.store.document(document_id)
        if doc is None: return None
        if not self.access.permitted(
            document_id,
            principal_id=principal_id,
            audience_id=audience_id,
        ):
            return None
        return {"document_id":doc.document_id,"source_kind":doc.source_kind.value,"source_uri":doc.source_uri,
            "version":doc.version,"retrieved_at":doc.retrieved_at.isoformat(),"content_hash":doc.content_hash,
            "active":self.lifecycle.active(document_id),
            "facts":tuple({"fact_id":f.fact_id,"statement":f.statement,"locator":f.locator} for f in self.store.facts_for(document_id)),
            "graph":self.index.graph_for_document(document_id)}
    def graph(
        self,entity:str,*,limit:int=20,
        principal_id:str|None=None,audience_id:str|None=None,
    )->tuple[dict[str,str],...]:
        return tuple(
            edge for edge in self.index.graph(entity,limit=limit)
            if self.lifecycle.active(edge["document_id"])
            and self.access.permitted(
                edge["document_id"],principal_id=principal_id,
                audience_id=audience_id,
            )
        )
    def write_document(self,relative_path:str,content:str,*,overwrite:bool=False)->dict[str,Any]:
        path=self._path(relative_path)
        if not isinstance(content,str): raise TypeError("content must be text")
        if path.exists() and not overwrite: raise FileExistsError("document already exists; explicit overwrite required")
        path.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=path.parent,prefix=path.name+".",suffix=".tmp") as fh:
            fh.write(content); tmp=Path(fh.name)
        tmp.replace(path)
        return {"path":path.relative_to(self.root).as_posix(),"bytes":len(content.encode("utf-8")),"overwritten":overwrite}
