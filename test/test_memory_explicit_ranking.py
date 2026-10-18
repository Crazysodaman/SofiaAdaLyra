from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.memory.model import MemoryRecord
from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.ranking import MemoryRankingService, RelevanceJudgment
from sofia.memory.system import MemorySystem
from sofia.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
SPARKS = PrincipalContext("sparks", "local:text", AudienceKind.PRIVATE)


def _promoted(store, content: str) -> MemoryCandidate:
    candidate = MemoryCandidate(
        candidate_id=uuid4(), content=content,
        sources=(SourceMessage(
            message_id=str(uuid4()), session_id="session-1", role="user",
            content="exact original", created_at=NOW, position=0,
        ),),
        created_at=NOW, principal_id="sparks", audience_id="local:text",
    )
    store.propose(candidate)
    store.promote(candidate.candidate_id)
    return candidate


def test_explicit_feedback_requires_same_eligible_private_retrieval(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    candidate = _promoted(store, "Artemis Docker recovery notes")
    ranking = MemoryRankingService(tmp_path / "sofia.db", store)
    system = MemorySystem(store, ranking_service=ranking)
    result = system.recall_relevant("Artemis Docker", principal=SPARKS)
    retrieval_id = ranking.last_retrieval_id(SPARKS)
    assert result and retrieval_id

    unknown = ranking.record_judgment(
        retrieval_id=retrieval_id, candidate_id=candidate.candidate_id,
        judgment=RelevanceJudgment.UNKNOWN, principal=SPARKS, at=NOW,
    )
    assert unknown.startswith("memory-judgment:")
    assert ranking.train(principal=SPARKS, at=NOW) is None
    assert ranking.diagnostics(principal=SPARKS)["judgments"] == {"unknown": 1}

    wrong_audience = PrincipalContext("sparks", "discord:dm", AudienceKind.PRIVATE)
    with pytest.raises(PermissionError):
        ranking.record_judgment(
            retrieval_id=retrieval_id, candidate_id=candidate.candidate_id,
            judgment=RelevanceJudgment.RELEVANT,
            principal=wrong_audience, at=NOW,
        )
    with pytest.raises(PermissionError):
        ranking.record_judgment(
            retrieval_id=retrieval_id, candidate_id=uuid4(),
            judgment=RelevanceJudgment.RELEVANT, principal=SPARKS, at=NOW,
        )


def test_calibrated_ranker_only_reorders_final_eligible_set_and_invalidates(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    preferred = _promoted(store, "Artemis Docker preferred recovery")
    other = _promoted(store, "Artemis Docker obsolete recovery")
    ranking = MemoryRankingService(tmp_path / "sofia.db", store)
    records = (
        MemoryRecord(str(other.candidate_id), other.content, NOW),
        MemoryRecord(str(preferred.candidate_id), preferred.content, NOW),
    )
    for index in range(4):
        when = NOW + timedelta(seconds=index)
        ranking.rank("Artemis Docker", records, principal=SPARKS, at=when)
        receipt = ranking.last_retrieval_id(SPARKS)
        ranking.record_judgment(
            retrieval_id=receipt, candidate_id=preferred.candidate_id,
            judgment=RelevanceJudgment.RELEVANT, principal=SPARKS, at=when,
            preferred_over_id=other.candidate_id,
        )
        ranking.record_judgment(
            retrieval_id=receipt, candidate_id=other.candidate_id,
            judgment=RelevanceJudgment.NOT_RELEVANT, principal=SPARKS,
            at=when + timedelta(microseconds=1),
        )
    model_id = ranking.train(principal=SPARKS, at=NOW + timedelta(minutes=1))
    assert model_id.startswith("memory-ranker:")
    ranked = ranking.rank(
        "Artemis Docker", records, principal=SPARKS,
        at=NOW + timedelta(minutes=2),
    )
    assert tuple(item.id for item in ranked) == (
        str(preferred.candidate_id), str(other.candidate_id),
    )
    # Reranking cannot append an ID, unlock another audience, or authorize work.
    assert {item.id for item in ranked} == {item.id for item in records}
    assert ranking.diagnostics(principal=SPARKS)["authority"] is False

    changed = ranking.invalidate_candidate(
        preferred.candidate_id, reason="owner correction", at=NOW + timedelta(minutes=3),
    )
    assert changed == 4
    assert ranking.diagnostics(principal=SPARKS)["model"]["status"] == "review_required"
    assert ranking.rank(
        "Artemis Docker", records, principal=SPARKS,
        at=NOW + timedelta(minutes=4),
    ) == records


def test_future_evaluation_reports_baseline_without_inventing_scorer_gain(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    candidate = _promoted(store, "Artemis Docker recovery timeline")
    ranking = MemoryRankingService(tmp_path / "sofia.db", store)
    records = (MemoryRecord(str(candidate.candidate_id), candidate.content, NOW),)
    ranking.rank("Artemis Docker", records, principal=SPARKS, at=NOW + timedelta(days=1))
    ranking.record_judgment(
        retrieval_id=ranking.last_retrieval_id(SPARKS),
        candidate_id=candidate.candidate_id,
        judgment=RelevanceJudgment.RELEVANT, principal=SPARKS,
        at=NOW + timedelta(days=1),
    )
    result = ranking.evaluate_future(principal=SPARKS, trained_before=NOW)
    assert result.sample_count == 1
    assert result.baseline_recall_at_5 == 1.0
    assert result.scorer_recall_at_5 is None
    assert result.scorer_ndcg_at_5 is None
    assert result.cross_audience_violations == 0
    assert result.independently_held_out is True


def test_canonical_revocation_reconciles_derived_model_without_review_hook(tmp_path):
    store = DurableMemoryCandidateStore(tmp_path / "sofia.db")
    first = _promoted(store, "Artemis Docker first")
    second = _promoted(store, "Artemis Docker second")
    ranking = MemoryRankingService(tmp_path / "sofia.db", store)
    records = (
        MemoryRecord(str(second.candidate_id), second.content, NOW),
        MemoryRecord(str(first.candidate_id), first.content, NOW),
    )
    for index in range(4):
        at = NOW + timedelta(seconds=index)
        ranking.rank("Artemis Docker", records, principal=SPARKS, at=at)
        receipt = ranking.last_retrieval_id(SPARKS)
        ranking.record_judgment(
            retrieval_id=receipt, candidate_id=first.candidate_id,
            judgment=RelevanceJudgment.RELEVANT, principal=SPARKS, at=at,
        )
        ranking.record_judgment(
            retrieval_id=receipt, candidate_id=second.candidate_id,
            judgment=RelevanceJudgment.NOT_RELEVANT, principal=SPARKS,
            at=at + timedelta(microseconds=1),
        )
    ranking.train(principal=SPARKS, at=NOW + timedelta(minutes=1))
    # Simulates a canonical lifecycle writer that does not call the app hook.
    store.revoke(first.candidate_id)
    remaining = (MemoryRecord(str(second.candidate_id), second.content, NOW),)
    assert ranking.rank(
        "Artemis Docker", remaining, principal=SPARKS,
        at=NOW + timedelta(minutes=2),
    ) == remaining
    assert ranking.diagnostics(principal=SPARKS)["model"]["status"] == "review_required"
