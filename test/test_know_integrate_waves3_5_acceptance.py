from datetime import datetime,timezone
from pathlib import Path

from sofia.knowledge import (
    DocumentDisposition,KnowledgeDocument,KnowledgeFact,SQLiteKnowledgeLifecycle,KnowledgeRetriever,
    KnowledgeStore,SourceKind,
)

NOW=datetime.now(timezone.utc)


def test_fact_supersession_drives_active_retrieval():
    store=KnowledgeStore()
    doc=KnowledgeDocument("d",SourceKind.MANUAL,"manual://breaker","1",NOW,"a"*64,True); store.register_document(doc)
    old=KnowledgeFact("f1","d","breaker torque is 10","p1",NOW)
    new=KnowledgeFact("f2","d","breaker torque is 12","p2",NOW,("f1",))
    store.record_fact(old); store.record_fact(new)
    assert store.active_facts()==(new,)
    hits=KnowledgeRetriever(store).search("breaker torque")
    assert hits and hits[0].fact==new

def test_untrusted_reference_is_excluded_by_default():
    store=KnowledgeStore()
    doc=KnowledgeDocument("d",SourceKind.MANUAL,"manual://x","1",NOW,"b"*64,False); store.register_document(doc)
    store.record_fact(KnowledgeFact("f","d","secret breaker detail","p1",NOW))
    assert KnowledgeRetriever(store).search("breaker")==()

def test_lifecycle_supersession_and_invalidation_are_durable(tmp_path:Path):
    p=tmp_path/"lifecycle.db"; life=SQLiteKnowledgeLifecycle(p)
    life.register("old"); life.register("new"); life.supersede("old","new"); life.invalidate("new")
    again=SQLiteKnowledgeLifecycle(p)
    assert again.status("old").disposition is DocumentDisposition.SUPERSEDED
    assert again.status("old").replaced_by=="new"
    assert again.status("new").disposition is DocumentDisposition.INVALID




def test_invalidated_document_is_not_retrieved(tmp_path:Path):
    store=KnowledgeStore()
    doc=KnowledgeDocument("d-invalid",SourceKind.MANUAL,"manual://old","1",NOW,"d"*64,True)
    store.register_document(doc)
    store.record_fact(KnowledgeFact("f-invalid","d-invalid","obsolete breaker value","p1",NOW))
    lifecycle=SQLiteKnowledgeLifecycle(tmp_path/"life.db")
    lifecycle.register("d-invalid")
    lifecycle.invalidate("d-invalid")
    assert KnowledgeRetriever(store,lifecycle).search("breaker")==()
