from datetime import datetime, timezone
import pytest
from sofia.knowledge import KnowledgeDocument, KnowledgeFact, KnowledgeStore, SourceKind
from sofia.integrate import AdapterManifest, AdapterRegistry, SideEffectClass, ToolInvocation

class Echo:
    manifest=AdapterManifest("echo","1","test",SideEffectClass.READ_ONLY,(),{}, {})
    def invoke(self,arguments): return dict(arguments)

def test_knowledge_requires_registered_provenance():
    store=KnowledgeStore()
    fact=KnowledgeFact("f","missing","x","L1",datetime.now(timezone.utc))
    with pytest.raises(KeyError): store.record_fact(fact)

def test_knowledge_records_document_and_fact():
    now=datetime.now(timezone.utc); store=KnowledgeStore()
    doc=KnowledgeDocument("d",SourceKind.MANUAL,"manual://x","1",now,"abc")
    store.register_document(doc); fact=KnowledgeFact("f","d","x","L1",now); store.record_fact(fact)
    assert store.fact("f")==fact

def test_registry_refuses_unauthorized_invocation():
    registry=AdapterRegistry(); registry.register(Echo())
    with pytest.raises(PermissionError): registry.invoke(ToolInvocation("i","echo",{},False))

def test_registry_returns_auditable_receipt():
    registry=AdapterRegistry(); registry.register(Echo())
    receipt=registry.invoke(ToolInvocation("i","echo",{"x":1},True))
    assert receipt.succeeded and receipt.output=={"x":1} and receipt.tool_id=="echo"
