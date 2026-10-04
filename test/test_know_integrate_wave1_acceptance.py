from datetime import datetime, timezone
import pytest
from sofia.knowledge import KnowledgeDocument, KnowledgeFact, KnowledgeStore, SourceKind


def test_knowledge_requires_registered_provenance():
    store=KnowledgeStore()
    fact=KnowledgeFact("f","missing","x","L1",datetime.now(timezone.utc))
    with pytest.raises(KeyError): store.record_fact(fact)

def test_knowledge_records_document_and_fact():
    now=datetime.now(timezone.utc); store=KnowledgeStore()
    doc=KnowledgeDocument("d",SourceKind.MANUAL,"manual://x","1",now,"abc")
    store.register_document(doc); fact=KnowledgeFact("f","d","x","L1",now); store.record_fact(fact)
    assert store.fact("f")==fact
