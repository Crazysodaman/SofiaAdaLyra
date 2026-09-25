from __future__ import annotations
from .model import KnowledgeDocument, KnowledgeFact

class KnowledgeStore:
    def __init__(self)->None:
        self._documents:dict[str,KnowledgeDocument]={}; self._facts:dict[str,KnowledgeFact]={}; self._by_document:dict[str,list[str]]={}
    def register_document(self, document:KnowledgeDocument)->None:
        old=self._documents.get(document.document_id)
        if old is not None and old != document: raise ValueError("document_id already registered with different provenance")
        self._documents[document.document_id]=document
    def record_fact(self,fact:KnowledgeFact)->None:
        if fact.document_id not in self._documents: raise KeyError("fact source document is not registered")
        old=self._facts.get(fact.fact_id)
        if old is not None and old != fact: raise ValueError("fact_id conflict")
        self._facts[fact.fact_id]=fact
        ids=self._by_document.setdefault(fact.document_id,[])
        if fact.fact_id not in ids: ids.append(fact.fact_id)
    def document(self,document_id:str): return self._documents.get(document_id)
    def fact(self,fact_id:str): return self._facts.get(fact_id)
    def facts_for(self,document_id:str)->tuple[KnowledgeFact,...]:
        return tuple(self._facts[x] for x in self._by_document.get(document_id,()))
