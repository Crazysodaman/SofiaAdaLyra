"""Capability surface for the operational KNOW service."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sofia.capability.model import Capability,CapabilityRequest
from sofia.cognition.model import CognitiveToolDefinition
from sofia.cognition.tools import CognitiveToolBinding
from sofia.safe.execution_approval import ExecutionApprovalVerifier
from sofia.safe.permissions import (
    PermissionLevel,
    PermissionStore,
    capability_permission_policy,
)
from .service import KnowledgeService

class KnowledgeCapabilitySet:
    _MUTATING=frozenset({
        "knowledge.ingest.text",
        "knowledge.ingest.pdf",
        "knowledge.document.write",
    })

    def __init__(
        self,
        service:KnowledgeService,
        *,
        approval_verifier:ExecutionApprovalVerifier,
        permission_store:PermissionStore|None=None,
    )->None:
        if not isinstance(approval_verifier,ExecutionApprovalVerifier):
            raise TypeError("approval_verifier must be ExecutionApprovalVerifier")
        if permission_store is not None and not isinstance(
            permission_store,PermissionStore
        ):
            raise TypeError("permission_store must be PermissionStore or None")
        self.service=service
        self.approval_verifier=approval_verifier
        self.permission_store=(
            permission_store
            if permission_store is not None
            else PermissionStore(approval_verifier.path)
        )

    def _authorize(self,name:str,p:dict[str,Any])->None:
        if name not in self._MUTATING:
            return
        policy=capability_permission_policy(name)
        if policy.level is PermissionLevel.SAFE_AUTONOMOUS:
            return
        approval_id=p.pop("approval_id",None)
        approval_parameters=dict(p)
        approval_parameters.pop("__principal_id",None)
        approval_parameters.pop("__audience_id",None)
        approval_parameters.pop("__audience_kind",None)
        if (
            policy.level is PermissionLevel.REVERSIBLE_SCOPED
            and self.permission_store.allows_standing(
                name,
                approval_parameters,
            )
        ):
            return
        if policy.level is PermissionLevel.NEVER_SELF_AUTHORIZED:
            raise PermissionError(
                "authority-changing knowledge operation cannot self-authorize"
            )
        self.approval_verifier.consume(
            approval_id=approval_id or "",
            capability=name,
            parameters=approval_parameters,
            now=datetime.now(timezone.utc),
        )
    @staticmethod
    def capabilities()->tuple[Capability,...]:
        return (
            Capability("knowledge.search","Search durable provenance-backed project knowledge."),
            Capability("knowledge.document","Read one durable knowledge document and its source facts."),
            Capability("knowledge.graph","Read provenance-linked knowledge graph edges."),
            Capability("knowledge.ingest.text","Ingest one authorized project text file into durable knowledge."),
            Capability("knowledge.ingest.pdf","Ingest one authorized project PDF/manual into durable knowledge."),
            Capability("knowledge.document.write","Write or replace one authorized project documentation file."),
        )
    def execute(self,request:CapabilityRequest)->Any:
        p=dict(request.parameters); name=request.capability.name
        self._authorize(name,p)
        principal_id=p.pop("__principal_id",None)
        audience_id=p.pop("__audience_id",None)
        p.pop("__audience_kind",None)
        if name=="knowledge.search": return self.service.search(
            p["query"],limit=p.get("limit",10),
            principal_id=principal_id,audience_id=audience_id,
        )
        if name=="knowledge.document": return self.service.document(
            p["document_id"],
            principal_id=principal_id,audience_id=audience_id,
        )
        if name=="knowledge.graph": return self.service.graph(
            p["entity"],limit=p.get("limit",20),
            principal_id=principal_id,audience_id=audience_id,
        )
        if name=="knowledge.ingest.text": return self.service.ingest_text(
            p["path"],version=p.get("version","local"),
            principal_id=principal_id,audience_id=audience_id,
        )
        if name=="knowledge.ingest.pdf": return self.service.ingest_pdf(
            p["path"],version=p.get("version","local"),
            principal_id=principal_id,audience_id=audience_id,
        )
        if name=="knowledge.document.write": return self.service.write_document(p["path"],p["content"],overwrite=bool(p.get("overwrite",False)))
        raise ValueError("unsupported KNOW capability")

def create_knowledge_tool_bindings()->tuple[CognitiveToolBinding,...]:
    def binding(tool_name,capability_name,description,properties,required=()):
        props=dict(properties)
        req=list(required)
        policy=capability_permission_policy(capability_name)
        if policy.level in {
            PermissionLevel.REVERSIBLE_SCOPED,
            PermissionLevel.PROTECTED,
        }:
            props["approval_id"]={"type":"string"}
            if policy.level is PermissionLevel.PROTECTED:
                req.append("approval_id")
        return CognitiveToolBinding(
            definition=CognitiveToolDefinition(
                name=tool_name,description=description,
                parameters={"type":"object","properties":props,"required":req,"additionalProperties":False},
            ),
            capability_name=capability_name,
            include_principal_metadata=True,
        )
    return (
        binding("search_knowledge","knowledge.search","Search Sofía's durable source-grounded project knowledge. Read-only.",
            {"query":{"type":"string"},"limit":{"type":"integer"}},("query",)),
        binding("inspect_knowledge_document","knowledge.document","Read a durable knowledge document and its provenance facts. Read-only.",
            {"document_id":{"type":"string"}},("document_id",)),
        binding("inspect_knowledge_graph","knowledge.graph","Read provenance-linked relationships for an exact knowledge entity. Read-only.",
            {"entity":{"type":"string"},"limit":{"type":"integer"}},("entity",)),
        binding("ingest_text_knowledge","knowledge.ingest.text","Ingest one authorized project text file into durable knowledge.",
            {"path":{"type":"string"},"version":{"type":"string"}},("path",)),
        binding("ingest_pdf_knowledge","knowledge.ingest.pdf","Ingest one authorized project PDF/manual into durable knowledge.",
            {"path":{"type":"string"},"version":{"type":"string"}},("path",)),
        binding("write_project_document","knowledge.document.write","Write a bounded project documentation file. Requires explicit write capability.",
            {"path":{"type":"string"},"content":{"type":"string"},"overwrite":{"type":"boolean"}},("path","content")),
    )
