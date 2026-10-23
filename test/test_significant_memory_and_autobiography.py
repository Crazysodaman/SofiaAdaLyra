"""B04: memory significance, autobiographical timeline, staleness fences."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.platform.application.memory_significance import MemorySignificanceService
from sofia.core.memory.autobiography import AutobiographyTimeline
from sofia.core.memory.originals import SourceMessage
from sofia.core.memory.provenance import MemoryCandidate
from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
from sofia.core.memory.significance import (
    MarkStatus, MemorySignificance, SignificantMemoryStore,
)
from sofia.core.life.model import ExperienceRecord
from sofia.core.life.store import LifeStore
from sofia.core.social.principals import local_sparks_principal

BASE = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


def candidate(text, *, index=0, principal="person:sparks", audience=None):
    at = BASE + timedelta(seconds=index)
    return MemoryCandidate(
        candidate_id=uuid4(), content=text,
        sources=(SourceMessage(
            f"source-{index}", "original-session", "user",
            "evidence for " + text, at, index,
        ),),
        created_at=at, principal_id=principal, audience_id=audience,
    )


def persisted(tmp_path):
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    path = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(path)
    candidates = DurableMemoryCandidateStore(path)
    significance = SignificantMemoryStore(path)
    return path, candidates, significance


def test_significance_cas_holds_and_rejects_changing_scope(tmp_path):
    _path, candidates, significance = persisted(tmp_path)
    item = candidate("She rebuilt the radio.", audience="local:text")
    candidates.propose(item)
    candidates.promote(item.candidate_id)
    mark = MemorySignificance(
        item.candidate_id, "person:sparks", "local:text", 0.9,
        "A first fully self-built artifact.", "person:sparks",
        1, MarkStatus.ACTIVE, BASE,
    )
    significance.hold(mark, expected_revision=None)
    assert significance.current(item.candidate_id).significance == 0.9
    revision = MemorySignificance(
        item.candidate_id, "person:sparks", "local:text", 0.6,
        "Recalibrated after review.", "person:sparks",
        2, MarkStatus.ACTIVE, BASE,
    )
    significance.hold(revision, expected_revision=1)
    assert significance.current(item.candidate_id).significance == 0.6
    with pytest.raises(RuntimeError, match="concurrently"):
        significance.hold(revision, expected_revision=None)
    with pytest.raises(RuntimeError, match="concurrently"):
        significance.hold(revision, expected_revision=0)
    cross_scope = MemorySignificance(
        item.candidate_id, "person:sparks", "discord:dm:999", 0.5,
        "Scope change attempt.", "person:sparks",
        3, MarkStatus.ACTIVE, BASE,
    )
    with pytest.raises(RuntimeError, match="scope cannot change"):
        significance.hold(cross_scope, expected_revision=2)
    assert [
        item.revision for item in significance.history(item.candidate_id)
    ] == [1, 2]


def test_significance_service_review_authority_and_promotion_gate(tmp_path):
    _path, candidate_store, significance = persisted(tmp_path)
    service = MemorySignificanceService(
        candidate_store=candidate_store, significance_store=significance,
    )
    sparks = local_sparks_principal()
    promoted = candidate(
        "She finished the antenna tuning.", index=1, audience="local:text",
    )
    candidate_store.propose(promoted)
    proposed_only = candidate("Only proposed text.", index=2)
    candidate_store.propose(proposed_only)

    with pytest.raises(PermissionError):
        service.mark(
            promoted.candidate_id, significance=0.8, reason="unrelated session",
            reviewed_by=local_sparks_principal(audience_id="remote-chat:xyz"),
            now=BASE,
        )
    with pytest.raises(LookupError):
        service.mark(
            uuid4(), significance=0.8, reason="missing", reviewed_by=sparks,
            now=BASE,
        )
    with pytest.raises(ValueError, match="promoted"):
        service.mark(
            proposed_only.candidate_id, significance=0.8, reason="not promoted",
            reviewed_by=sparks, now=BASE,
        )
    candidate_store.promote(promoted.candidate_id)
    revoked = candidate("Revoked before marking.", index=3)
    candidate_store.propose(revoked)
    candidate_store.promote(revoked.candidate_id)
    candidate_store.revoke(revoked.candidate_id)
    with pytest.raises(ValueError, match="only promoted candidates"):
        service.mark(
            revoked.candidate_id, significance=0.7, reason="already revoked",
            reviewed_by=sparks, now=BASE,
        )
    expired = candidate("Expired workaround note.", index=4)
    candidate_store.propose(expired)
    candidate_store.promote(expired.candidate_id)
    candidate_store.set_expiration(
        expired.candidate_id, expires_at=BASE - timedelta(days=1),
        reviewed_by="person:sparks", reason="Time-bounded note.",
    )
    with pytest.raises(ValueError, match="stale memory candidate"):
        service.mark(
            expired.candidate_id, significance=0.7, reason="already stale",
            reviewed_by=sparks, now=BASE,
        )
    mark = service.mark(
        promoted.candidate_id, significance=0.95,
        reason="First successful antenna tuning.", reviewed_by=sparks,
        now=BASE,
    )
    assert mark.revision == 1 and mark.status is MarkStatus.ACTIVE
    withdrawn = service.withdraw(
        promoted.candidate_id, reason="Review changed.", reviewed_by=sparks,
        now=BASE + timedelta(minutes=1),
    )
    assert withdrawn.status is MarkStatus.REVOKED and withdrawn.revision == 2
    with pytest.raises(ValueError, match="no active significance"):
        service.withdraw(
            promoted.candidate_id, reason="Nothing left.",
            reviewed_by=sparks, now=BASE,
        )


def test_timeline_gates_foreign_audiences_and_includes_significance(tmp_path):
    path, candidate_store, significance = persisted(tmp_path)
    timeline = AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    )
    built = candidate("She rebuilt the amplifier.", index=1, audience=None)
    candidate_store.propose(built)
    candidate_store.promote(built.candidate_id)
    service = MemorySignificanceService(
        candidate_store=candidate_store, significance_store=significance,
    )
    service.mark(
        built.candidate_id, significance=0.85, reason="First amplifier.",
        reviewed_by=local_sparks_principal(), now=BASE,
    )
    foreign = AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    ).entries(principal=local_sparks_principal(audience_id="discord:dm:42"))
    assert foreign == ()
    assert foreign == AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    ).entries(
        principal=local_sparks_principal(audience_id="remote-chat:abc"),
    )
    entries = timeline.entries(principal=local_sparks_principal())
    memory_entries = [entry for entry in entries if entry.kind == "memory"]
    assert len(memory_entries) == 1
    assert memory_entries[0].summary == "She rebuilt the amplifier."
    assert memory_entries[0].significance == 0.85
    assert memory_entries[0].anchor.startswith("memory:")
    with pytest.raises(ValueError, match="limit"):
        timeline.entries(
            principal=local_sparks_principal(), limit=257,
        )


def test_timeline_excludes_stale_and_revoked_sources_and_combines_experiences(tmp_path):
    path, candidate_store, significance = persisted(tmp_path)
    store = LifeStore(path)
    timeline = AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    )
    revoked = candidate("Old claim about a workshop.", index=1)
    candidate_store.propose(revoked)
    candidate_store.promote(revoked.candidate_id)
    candidate_store.revoke(revoked.candidate_id)
    valid = candidate("Verified workshop note.", index=2)
    candidate_store.propose(valid)
    candidate_store.promote(valid.candidate_id)
    corrected = candidate("Corrected workshop note.", index=3)
    candidate_store.propose(corrected)
    candidate_store.link_correction(corrected.candidate_id, valid.candidate_id)
    candidate_store.promote(corrected.candidate_id)

    experience = ExperienceRecord(
        "experience:workshop-1", None, "artifact_evaluated",
        "One workshop evening produced the coil winding.", ("evidence:test:1",),
        "local:text", False, BASE + timedelta(days=5), BASE + timedelta(days=5),
        {},
    )
    store.record_experience(experience)

    entries = timeline.entries(principal=local_sparks_principal())
    summaries = [entry.summary for entry in entries]
    assert "Old claim about a workshop." not in summaries
    assert "Verified workshop note." not in summaries
    assert "Corrected workshop note." in summaries
    assert "One workshop evening produced the coil winding." in summaries
    anchors = {entry.anchor: entry for entry in entries}
    assert "experience:workshop-1" in anchors
    memories = [
        entry for entry in entries
        if entry.kind == "memory" and entry.significance is None
    ]
    assert memories, "memory entries without marks stay significance-less"
    ordered = [entry.occurred_at for entry in entries]
    assert ordered == sorted(ordered, reverse=True)

    restarted = AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    ).entries(principal=local_sparks_principal())
    assert restarted == entries


def test_timeline_quotes_only_current_ga_episode_outcomes_fail_closed(tmp_path):
    from sofia.core.generalization.advanced import (
        AdvancedGeneralizationStore, EpisodePhase,
    )
    from sofia.core.generalization.contracts import ExplorationAdmission
    from sofia.core.goals import GoalStore
    from sofia.core.goals.service import GoalService
    from sofia.core.learning.contracts import DataUseGrant
    from sofia.platform.state.sqlite_plane import SQLiteStatePlane

    path, candidate_store, significance = persisted(tmp_path)
    SQLiteStatePlane(path)
    now_real = datetime.now(timezone.utc)

    class _Learning:
        def active_grant(self, *, principal_id, audience_id, purpose, required, at):
            return DataUseGrant(
                "grant:ga-timeline", principal_id, audience_id, purpose,
                frozenset(required), now_real - timedelta(hours=1),
                now_real + timedelta(days=60), "owner-ui:ga-timeline",
            )

    advanced = AdvancedGeneralizationStore(
        path, goals=GoalService(GoalStore(SQLiteStatePlane(path))),
        admission=lambda: ExplorationAdmission(), learning=_Learning(),
    )
    from sofia.core.goals.evidence import GoalEvidenceLedger
    ledger = GoalEvidenceLedger(path)
    refs = []
    for index, kind in enumerate((
        "reviewed_evidence", "reviewed_evidence", "reviewed_evidence",
        "reviewed_evidence", "operation_receipt",
    )):
        ref = f"episode-timeline:{index}"
        ledger.record(
            evidence_ref=ref, kind=kind, observed_at=now_real,
            source="ops:ga-timeline-test", successful=False if index == 4 else None,
            principal_id="person:sparks", audience="local:text",
        )
        refs.append(ref)
    sparks = local_sparks_principal()
    advanced.record_episode(
        principal=sparks, subject_id="device:radio",
        context_tags=("radio", "repair"),
        phases=tuple(
            EpisodePhase(
                kind, f"Recorded {kind} for the radio repair.", (refs[index],),
            )
            for index, kind in enumerate(
                ("intent", "observation", "hypothesis", "action", "outcome"),
            )
        ),
        occurred_at=now_real, retention_until=now_real + timedelta(days=30),
        now=now_real,
    )
    timeline = AutobiographyTimeline(
        state_path=path, candidate_store=candidate_store,
        significance_store=significance,
    )
    entries = timeline.entries(principal=sparks)
    episode_entries = [entry for entry in entries if entry.kind == "episode"]
    assert [entry.summary for entry in episode_entries] == [
        "Recorded outcome for the radio repair.",
    ]
    assert episode_entries[0].anchor.startswith("ga-episode:")
    assert timeline.entries(
        principal=local_sparks_principal(audience_id="discord:dm:9"),
    ) == ()

    changed = advanced.propagate_revocations(now=now_real + timedelta(days=31))
    assert changed["episodes_expired"] == 1
    assert [
        entry for entry in timeline.entries(principal=sparks)
        if entry.kind == "episode"
    ] == []
