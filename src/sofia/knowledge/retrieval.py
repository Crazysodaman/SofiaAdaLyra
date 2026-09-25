"""Small deterministic provenance-first knowledge retrieval."""
from __future__ import annotations
from dataclasses import dataclass
import re
from .model import KnowledgeFact
from .store import KnowledgeStore

@dataclass(frozen=True)
class KnowledgeHit:
    fact: KnowledgeFact
    score: int
    source_uri: str
    source_version: str

def _tokens(text:str)->set[str]:
    return {x for x in re.findall(r"[a-z0-9_./:-]+",text.lower()) if len(x)>1}

class KnowledgeRetriever:
    def __init__(self,store:KnowledgeStore)->None: self.store=store
    def search(self,query:str,*,trusted_only:bool=True,limit:int=10)->tuple[KnowledgeHit,...]:
        if not query.strip(): return ()
        q=_tokens(query); hits=[]
        for fact in self.store.active_facts():
            doc=self.store.document(fact.document_id)
            if doc is None or (trusted_only and not doc.trusted_for_reference): continue
            score=len(q & _tokens(fact.statement+" "+fact.locator+" "+doc.source_uri))
            if score: hits.append(KnowledgeHit(fact,score,doc.source_uri,doc.version))
        hits.sort(key=lambda h:(-h.score,h.fact.fact_id))
        return tuple(hits[:max(0,limit)])
