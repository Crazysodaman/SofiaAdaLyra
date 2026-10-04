from datetime import datetime,timezone
from pathlib import Path
import pytest
from sofia.knowledge.service import KnowledgeService
from sofia.knowledge.lifecycle import SQLiteKnowledgeLifecycle
from sofia.knowledge.persistence import SQLiteKnowledgeStore
from sofia.integrate.schema import validate_object,SchemaValidationError

def test_local_ingest_hashes_and_reads(tmp_path:Path):
    p=tmp_path/"doc.txt"; p.write_text("hello",encoding="utf-8")
    service=KnowledgeService(tmp_path,SQLiteKnowledgeStore(tmp_path/"sofia.db"),SQLiteKnowledgeLifecycle(tmp_path/"sofia.db"))
    result=service.ingest_text("doc.txt")
    doc=service.store.document(result["document_id"]); text=p.read_text(encoding="utf-8")
    assert text=="hello" and len(doc.content_hash)==64

def test_durable_store_round_trip(tmp_path:Path):
    p=tmp_path/"doc.txt"; p.write_text("hello",encoding="utf-8")
    service=KnowledgeService(tmp_path,SQLiteKnowledgeStore(tmp_path/"sofia.db"),SQLiteKnowledgeLifecycle(tmp_path/"sofia.db"))
    result=service.ingest_text("doc.txt"); doc=service.store.document(result["document_id"])
    s=SQLiteKnowledgeStore(tmp_path/"knowledge.db"); s.register_document(doc)
    assert SQLiteKnowledgeStore(tmp_path/"knowledge.db").document(doc.document_id)==doc

def test_schema_rejects_missing_required():
    with pytest.raises(SchemaValidationError): validate_object({"type":"object","required":["x"]},{})
