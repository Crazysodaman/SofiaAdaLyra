"""Capability surface for the operational KNOW service."""
from __future__ import annotations
from typing import Any
from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from .service import KnowledgeService

class KnowledgeCapabilitySet:
    def __init__(self,service:KnowledgeService)->None: self.service=service
    @staticmethod
    def capabilities()->tuple[Capability,...]:
        return (
            Capability("knowledge.search","Search durable provenance-backed project knowledge."),
            Capability("knowledge.document","Read one durable knowledge document and its source facts."),
            Capability("knowledge.ingest.text","Ingest one authorized project text file into durable knowledge."),
            Capability("knowledge.ingest.pdf","Ingest one authorized project PDF/manual into durable knowledge."),
            Capability("knowledge.document.write","Write or replace one authorized project documentation file."),
        )
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); name=request.capability.name
        if name=="knowledge.search": return self.service.search(p["query"],limit=p.get("limit",10))
        if name=="knowledge.document": return self.service.document(p["document_id"])
        if name=="knowledge.ingest.text": return self.service.ingest_text(p["path"],version=p.get("version","local"))
        if name=="knowledge.ingest.pdf": return self.service.ingest_pdf(p["path"],version=p.get("version","local"))
        if name=="knowledge.document.write": return self.service.write_document(p["path"],p["content"],overwrite=bool(p.get("overwrite",False)))
        raise ValueError("unsupported KNOW capability")

def create_knowledge_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def binding(tool_name,capability_name,description,properties,required=()):
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name=tool_name,description=description,
                parameters={"type":"object","properties":properties,"required":list(required),"additionalProperties":False},
            ),
            capability_name=capability_name,
        )
    return (
        binding("search_knowledge","knowledge.search","Search Sofía's durable source-grounded project knowledge. Read-only.",
            {"query":{"type":"string"},"limit":{"type":"integer"}},("query",)),
        binding("inspect_knowledge_document","knowledge.document","Read a durable knowledge document and its provenance facts. Read-only.",
            {"document_id":{"type":"string"}},("document_id",)),
        binding("ingest_text_knowledge","knowledge.ingest.text","Ingest one authorized project text file into durable knowledge.",
            {"path":{"type":"string"},"version":{"type":"string"}},("path",)),
        binding("ingest_pdf_knowledge","knowledge.ingest.pdf","Ingest one authorized project PDF/manual into durable knowledge.",
            {"path":{"type":"string"},"version":{"type":"string"}},("path",)),
        binding("write_project_document","knowledge.document.write","Write a bounded project documentation file. Requires explicit write capability.",
            {"path":{"type":"string"},"content":{"type":"string"},"overwrite":{"type":"boolean"}},("path","content")),
    )
