from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from sofia.capability.model import CapabilityResult, CapabilityResultKind
from sofia.cognition.v2.contracts import (
    ActionRequirement, ConversationFocus, EvidenceNeed, TurnKernelInput,
)
from sofia.cognition.v2.matrix import MatrixV2Planner
from sofia.cognition.v2.evidence import CognitiveEvidenceLedger, EvidenceAcquisitionCoordinator
from sofia.knowledge.evidence import KnowledgeEvidenceCoordinator
from sofia.knowledge.index import KnowledgeIndex
from sofia.knowledge.lifecycle import DocumentDisposition, SQLiteKnowledgeLifecycle
from sofia.knowledge.persistence import SQLiteKnowledgeStore
from sofia.knowledge.service import KnowledgeService


def _service(root: Path, *, index=None):
    state = root / "sofia.db"
    store = SQLiteKnowledgeStore(state)
    lifecycle = SQLiteKnowledgeLifecycle(state)
    return KnowledgeService(
        root, store, lifecycle,
        index=index,
    )


def test_structured_ingestion_exact_identifier_provenance_and_privacy(tmp_path):
    (tmp_path / "manual.md").write_text(
        "# Artemis networking\n\nExact service ID ArtemisNode-77 owns the uplink.\n"
        "\n## Recovery\n\nRestart only after collecting latency evidence.\n",
        encoding="utf-8",
    )
    service = _service(tmp_path)
    result = service.ingest_text(
        "manual.md", version="v1", principal_id="sparks", audience_id="private",
    )

    hits = service.search(
        "ArtemisNode-77", principal_id="sparks", audience_id="private",
    )

    assert hits[0]["document_id"] == result["document_id"]
    assert hits[0]["heading"] == "Artemis networking"
    assert hits[0]["locator"].startswith("lines ")
    assert len(hits[0]["content_hash"]) == 64
    assert hits[0]["exact_match"] is True
    assert service.search(
        "ArtemisNode-77", principal_id="someone-else", audience_id="public",
    ) == ()


def test_incremental_reindex_and_stale_revision_are_deterministic(tmp_path):
    path = tmp_path / "guide.md"
    path.write_text("# Status\nOldIdentifier is current.\n", encoding="utf-8")
    service = _service(tmp_path)
    first = service.ingest_text("guide.md", version="1")
    duplicate = service.ingest_text("guide.md", version="1")
    assert duplicate["document_id"] == first["document_id"]

    path.write_text("# Status\nNewIdentifier is current.\n", encoding="utf-8")
    second = service.ingest_text("guide.md", version="2")

    assert second["document_id"] != first["document_id"]
    status = service.lifecycle.status(first["document_id"])
    assert status.disposition is DocumentDisposition.SUPERSEDED
    assert status.replaced_by == second["document_id"]
    assert service.search("OldIdentifier") == ()
    assert service.search("NewIdentifier")[0]["source_version"] == "2"


def test_optional_embeddings_add_semantic_candidates_without_replacing_provenance(tmp_path):
    def embed(text):
        lowered = text.casefold()
        return (
            1.0 if any(word in lowered for word in ("latency", "delay", "slow")) else 0.0,
            1.0 if "wardrobe" in lowered else 0.0,
        )

    index = KnowledgeIndex(tmp_path / "sofia.db", embedding_provider=embed)
    (tmp_path / "ops.md").write_text(
        "# Network behavior\nRound-trip latency rises under congestion.\n",
        encoding="utf-8",
    )
    service = _service(tmp_path, index=index)
    service.ingest_text("ops.md")

    hits = service.search("why is the response slow")

    assert hits[0]["heading"] == "Network behavior"
    assert hits[0]["semantic_score"] > 0.9
    assert hits[0]["source_uri"].endswith("ops.md")


def test_knowledge_graph_edges_retain_document_and_section_sources(tmp_path):
    (tmp_path / "links.md").write_text(
        "# Artemis\nSee [Fleet runbook](docs/fleet.md).\n", encoding="utf-8",
    )
    service = _service(tmp_path)
    result = service.ingest_text("links.md")

    edges = service.graph("Fleet runbook")

    assert edges[0]["target"] == "docs/fleet.md"
    assert edges[0]["document_id"] == result["document_id"]
    assert edges[0]["section_id"].startswith(result["document_id"])


class Dispatcher:
    def dispatch(self, tool, *, principal, allowed_capabilities):
        assert tool.name == "search_knowledge"
        assert allowed_capabilities == ("knowledge.search",)
        return CapabilityResult(
            "knowledge.search",
            CapabilityResultKind.SUCCESS,
            evidence=({
                "document_id": "doc-1", "heading": "Docker recovery",
                "statement": "Collect logs before restarting Docker.",
                "locator": "lines 10-12", "source_uri": "file:///manual.md",
            },),
        )


def test_knowledge_retrieval_enters_the_v2_evidence_ledger(tmp_path):
    need = EvidenceNeed(
        "need:know:1", "runtime:sofia", "knowledge.retrieval",
        "audience:private", max_age_seconds=300, minimum_trust=0.6,
    )
    plan = SimpleNamespace(
        turn_id="turn-1", evidence_needs=(need,),
        action_requirement=ActionRequirement.NONE,
    )
    ledger = CognitiveEvidenceLedger(tmp_path / "sofia.db")
    coordinator = KnowledgeEvidenceCoordinator(
        Dispatcher(), EvidenceAcquisitionCoordinator(ledger),
    )

    response = coordinator.answer(
        plan=plan, focus=SimpleNamespace(), principal=None,
        allowed_capabilities=("knowledge.search",),
        query="Docker recovery manual",
    )

    assert "Docker recovery" in response.content
    assert response.evidence_refs[0] == "capability:knowledge.search"
    atoms = ledger.matching(need)
    assert len(atoms) == 1
    assert atoms[0].source_id == "capability:knowledge.search"


def test_matrix_v2_requests_scoped_knowledge_retrieval():
    turn = TurnKernelInput(
        turn_id="turn-know", session_id="session-1",
        content="Search the documentation for Artemis latency",
        created_at=datetime.now(timezone.utc), channel="desktop",
        principal_id="sparks", audience_id="audience:private",
    )
    focus = ConversationFocus(
        session_id="session-1", audience_id="audience:private", revision=1,
    )

    plan = MatrixV2Planner().plan(turn, focus)

    need = next(item for item in plan.evidence_needs if item.predicate == "knowledge.retrieval")
    assert need.scope_id == "audience:private"
