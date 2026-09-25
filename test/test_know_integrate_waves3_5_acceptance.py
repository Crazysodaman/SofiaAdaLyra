from datetime import datetime,timezone
from pathlib import Path
import pytest

from sofia.capability import Capability,CapabilitySystem
from sofia.integrate import (
    AdapterDisabledError,AdapterManifest,CapabilitySystemAdapter,DuplicateInvocationError,
    GovernedAdapterRegistry,InvocationContext,JsonlReceiptLedger,SideEffectClass,ToolInvocation,
)
from sofia.knowledge import (
    DocumentDisposition,KnowledgeDocument,KnowledgeFact,KnowledgeLifecycle,KnowledgeRetriever,
    KnowledgeStore,RepositoryIngestError,SourceKind,ingest_repository_file,
)

NOW=datetime.now(timezone.utc)

def test_repository_ingest_is_revisioned_and_root_confined(tmp_path:Path):
    root=tmp_path/"repo"; root.mkdir(); (root/"docs").mkdir(); (root/"docs"/"a.md").write_text("breaker manual",encoding="utf-8")
    doc,text=ingest_repository_file(root,"docs/a.md",document_id="d1",revision="abc123")
    assert text=="breaker manual" and doc.version=="abc123" and doc.source_kind is SourceKind.REPOSITORY
    outside=tmp_path/"outside.txt"; outside.write_text("no",encoding="utf-8")
    with pytest.raises(RepositoryIngestError): ingest_repository_file(root,"../outside.txt",document_id="d2",revision="abc123")

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
    p=tmp_path/"lifecycle.json"; life=KnowledgeLifecycle(p)
    life.register("old"); life.register("new"); life.supersede("old","new"); life.invalidate("new")
    again=KnowledgeLifecycle(p)
    assert again.status("old").disposition is DocumentDisposition.SUPERSEDED
    assert again.status("old").replaced_by=="new"
    assert again.status("new").disposition is DocumentDisposition.INVALID

class Echo:
    manifest=AdapterManifest("echo","1","tests",SideEffectClass.READ_ONLY,("ops.inspect",),
        {"type":"object","required":["value"],"properties":{"value":{}},"additionalProperties":False},
        {"type":"object","required":["echo"],"properties":{"echo":{}},"additionalProperties":False})
    def invoke(self,arguments): return {"echo":arguments["value"]}

def test_governed_registry_requires_enable_capability_side_effect_and_dedupes(tmp_path:Path):
    ledger=JsonlReceiptLedger(tmp_path/"receipts.jsonl"); reg=GovernedAdapterRegistry(ledger); reg.register(Echo())
    req=ToolInvocation("i1","echo",{"value":"x"},True)
    ctx=InvocationContext("Sparks",frozenset({"ops.inspect"}),frozenset({SideEffectClass.READ_ONLY}))
    with pytest.raises(AdapterDisabledError): reg.invoke(req,ctx)
    reg.enable("echo","1")
    with pytest.raises(PermissionError):
        reg.invoke(req,InvocationContext("Sparks",frozenset(),frozenset({SideEffectClass.READ_ONLY})))
    receipt=reg.invoke(req,ctx); assert receipt.succeeded and receipt.output=={"echo":"x"}
    assert JsonlReceiptLedger(tmp_path/"receipts.jsonl").get("i1") is not None
    with pytest.raises(DuplicateInvocationError): reg.invoke(req,ctx)

def test_capability_adapter_uses_existing_authority_boundary():
    system=CapabilitySystem(lambda request: True)
    cap=Capability("system.inspect","inspect system")
    system.register(cap,lambda request: {"hostname":"venus"})
    adapter=CapabilitySystemAdapter(system,tool_id="system.inspect.adapter",capability_name="system.inspect")
    out=adapter.invoke({})
    assert out["kind"]=="success" and out["evidence"]["hostname"]=="venus"
