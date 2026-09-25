from datetime import datetime,timezone
from pathlib import Path
import pytest
from sofia.knowledge.ingest import ingest_local_file
from sofia.knowledge.persistence import JsonKnowledgeStore
from sofia.integrate.schema import validate_object,SchemaValidationError

def test_local_ingest_hashes_and_reads(tmp_path:Path):
    p=tmp_path/"doc.txt"; p.write_text("hello",encoding="utf-8")
    doc,text=ingest_local_file(p,document_id="d1")
    assert text=="hello" and len(doc.content_hash)==64

def test_durable_store_round_trip(tmp_path:Path):
    p=tmp_path/"doc.txt"; p.write_text("hello",encoding="utf-8")
    doc,_=ingest_local_file(p,document_id="d1")
    s=JsonKnowledgeStore(tmp_path/"knowledge.json"); s.register_document(doc); s.flush()
    assert JsonKnowledgeStore(tmp_path/"knowledge.json").document("d1")==doc

def test_schema_rejects_missing_required():
    with pytest.raises(SchemaValidationError): validate_object({"type":"object","required":["x"]},{})
