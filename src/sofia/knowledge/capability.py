"""CapabilitySystem bindings for provenance-aware knowledge reads and search."""
from __future__ import annotations

from pathlib import Path

from sofia.capability.model import Capability, CapabilityRequest
from sofia.knowledge.lifecycle import KnowledgeLifecycle
from sofia.knowledge.persistence import JsonKnowledgeStore
from sofia.knowledge.repository_ingest import ingest_repository_file
from sofia.knowledge.retrieval import KnowledgeRetriever

KNOWLEDGE_SOURCE_READ_CAPABILITY = Capability(
    "knowledge.source.read",
    "Read one repository text source with versioned provenance.",
)
KNOWLEDGE_SEARCH_CAPABILITY = Capability(
    "knowledge.search",
    "Search durable trusted knowledge facts with provenance.",
)

class KnowledgeSourceReadCapability:
    capability = KNOWLEDGE_SOURCE_READ_CAPABILITY

    def __init__(self, repository_root: Path) -> None:
        self._root = repository_root.resolve()

    def execute(self, request: CapabilityRequest):
        path = request.parameters.get("path")
        version = request.parameters.get("version")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("knowledge source path is required")
        if not isinstance(version, str) or not version.strip():
            raise ValueError("knowledge source version is required")
        document_id = request.parameters.get("document_id", path)
        if not isinstance(document_id, str) or not document_id.strip():
            raise ValueError("knowledge document_id must be a non-empty string")
        document, text = ingest_repository_file(
            self._root,
            path,
            document_id=document_id,
            revision=version,
        )
        return {
            "document": {
                "document_id": document.document_id,
                "source_kind": document.source_kind.value,
                "source_uri": document.source_uri,
                "version": document.version,
                "retrieved_at": document.retrieved_at.isoformat(),
                "content_hash": document.content_hash,
                "trusted_for_reference": document.trusted_for_reference,
            },
            "content": text,
        }

class KnowledgeSearchCapability:
    capability = KNOWLEDGE_SEARCH_CAPABILITY

    def __init__(
        self,
        store: JsonKnowledgeStore,
        lifecycle: KnowledgeLifecycle,
    ) -> None:
        self._retriever = KnowledgeRetriever(store, lifecycle)

    def execute(self, request: CapabilityRequest):
        query = request.parameters.get("query")
        limit = request.parameters.get("limit", 10)
        if not isinstance(query, str) or not query.strip():
            raise ValueError("knowledge search query is required")
        if type(limit) is not int or limit < 1 or limit > 50:
            raise ValueError("knowledge search limit must be 1..50")
        hits = self._retriever.search(query, limit=limit)
        return {
            "hits": [
                {
                    "fact_id": hit.fact.fact_id,
                    "statement": hit.fact.statement,
                    "locator": hit.fact.locator,
                    "document_id": hit.fact.document_id,
                    "source_uri": hit.source_uri,
                    "source_version": hit.source_version,
                    "score": hit.score,
                }
                for hit in hits
            ]
        }
