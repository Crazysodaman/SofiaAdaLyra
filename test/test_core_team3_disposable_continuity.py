"""CORE-003 synthetic identity + reviewed-memory restart contract.

Disposable files only. No personal Core, Ollama, Fleet, or production state.
This is a cross-store test; it does not constitute G8 real-host acceptance.
"""
from datetime import datetime, timezone
from hashlib import sha256
import sqlite3
from uuid import uuid4

import pytest

from sofia.core.constitution.store import (
    ConstitutionIntegrityError,
    ConstitutionIntegrityVerifier,
    ConstitutionStore,
)
from sofia.core.conversation.model import ConversationMessage, ConversationRole
from sofia.core.conversation.store import ConversationStore
from sofia.core.identity.model import IdentityBootstrapMode
from sofia.core.identity.store import IdentityStore, IdentityStoreError
from sofia.core.memory.provenance import CandidateStatus
from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
from sofia.core.personality.model import PersonalityProfile
from sofia.core.personality.store import PersonalityStore, PersonalityStoreError
from sofia.core.social.principals import local_sparks_principal
from sofia.core.social.store import SocialSessionStore
from sofia.platform.application.memory_review import MemoryReviewService
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


def _seed(home):
    constitution = home / "constitution.md"
    trusted_hash = home / "constitution.sha256"
    original_rule = "Owner approval is required for a protected change.\n"
    constitution.write_text(original_rule, encoding="utf-8")
    trusted_hash.write_text(
        sha256(original_rule.encode("utf-8")).hexdigest() + "\n",
        encoding="utf-8",
    )

    identity_path = home / "identity.json"
    original_identity = IdentityStore(identity_path).load()
    personality_path = home / "personality.json"
    original_personality = PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=("curious", "analytical", "direct"),
        communication_style="Clear and skeptical.",
    )
    PersonalityStore(personality_path).save(original_personality)

    state = bootstrap_canonical_sqlite(home / "sofia.db")
    conversations = ConversationStore(state)
    candidates = DurableMemoryCandidateStore(state)
    owner = local_sparks_principal()
    session = conversations.create_session()
    SocialSessionStore(state).bind(session_id=session.id, principal=owner)
    original = ConversationMessage(
        id=str(uuid4()), session_id=session.id, role=ConversationRole.USER,
        content="Remember: the synthetic sensor is violet.",
        created_at=datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc),
    )
    conversations.save(original)
    pending = MemoryReviewService(
        conversation_store=conversations,
        candidate_store=candidates,
        state_path=state,
    ).propose(
        session_id=session.id,
        message_ids=(original.id,),
        content="The synthetic sensor is violet.",
        created_at=original.created_at,
    )
    assert candidates.status(pending.candidate_id) is CandidateStatus.PROPOSED
    candidates.close()
    conversations.close()
    return {
        "identity": original_identity,
        "personality": original_personality,
        "session_id": session.id,
        "message": original,
        "candidate_id": pending.candidate_id,
        "owner": owner,
        "state": state,
    }


def _reopen(home):
    identity = IdentityStore(
        home / "identity.json",
        bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    ).load()
    personality = PersonalityStore(home / "personality.json").load()
    constitution = ConstitutionStore(home / "constitution.md").load()
    ConstitutionIntegrityVerifier(
        str(home / "constitution.sha256")
    ).verify(constitution)
    conversations = ConversationStore(home / "sofia.db")
    candidates = DurableMemoryCandidateStore(home / "sofia.db")
    reviewer = MemoryReviewService(
        conversation_store=conversations,
        candidate_store=candidates,
        state_path=home / "sofia.db",
    )
    return identity, personality, conversations, candidates, reviewer


def test_disposable_identity_personality_and_reviewed_memory_survive_restart(tmp_path):
    before = _seed(tmp_path)
    identity, personality, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        assert identity == before["identity"]
        assert personality == before["personality"]
        assert conversations.get_session(before["session_id"]) is not None
        assert conversations.list_messages(before["session_id"]) == (before["message"],)
        original_candidate = candidates.get(before["candidate_id"])
        assert original_candidate is not None
        assert original_candidate.sources[0].message_id == before["message"].id
        reviewer.promote(before["candidate_id"], approved_by=before["owner"])
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert candidates.is_recall_eligible(before["candidate_id"])
    finally:
        candidates.close()
        conversations.close()


@pytest.mark.parametrize("tamper", ("original", "audience"))
def test_restart_blocks_promoting_changed_original_or_audience(tmp_path, tamper):
    before = _seed(tmp_path)
    with sqlite3.connect(before["state"]) as database:
        if tamper == "original":
            database.execute(
                "UPDATE conversation_messages SET content=? WHERE id=?",
                ("changed after initial review", before["message"].id),
            )
        else:
            database.execute(
                "UPDATE social_session_principal SET audience_id=? WHERE session_id=?",
                ("discord:dm:synthetic-other", before["session_id"]),
            )
    identity, personality, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        assert identity == before["identity"]
        assert personality == before["personality"]
        with pytest.raises((PermissionError, LookupError)):
            reviewer.promote(before["candidate_id"], approved_by=before["owner"])
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()


def test_restart_rejects_invalid_authority_files_without_regeneration(tmp_path):
    before = _seed(tmp_path)
    (tmp_path / "identity.json").write_text(
        '{"name": "Sofía Ada Lyra", "instance_id": "invalid"}',
        encoding="utf-8",
    )
    with pytest.raises(IdentityStoreError):
        IdentityStore(
            tmp_path / "identity.json",
            bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
        ).load()
    assert before["state"].exists()

    (tmp_path / "personality.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(PersonalityStoreError):
        PersonalityStore(tmp_path / "personality.json").load()

    (tmp_path / "constitution.md").write_text(
        "Model can rewrite authoritative state.\n", encoding="utf-8",
    )
    with pytest.raises(ConstitutionIntegrityError):
        ConstitutionIntegrityVerifier(
            str(tmp_path / "constitution.sha256")
        ).verify(ConstitutionStore(tmp_path / "constitution.md").load())


def _prepare_reviewed_correction(home):
    """Both memories use current originals under the same owner-bound session."""
    before = _seed(home)
    _, _, conversations, candidates, reviewer = _reopen(home)
    try:
        reviewer.promote(before["candidate_id"], approved_by=before["owner"])
        replacement_original = ConversationMessage(
            id=str(uuid4()), session_id=before["session_id"],
            role=ConversationRole.USER,
            content="Correction: the synthetic sensor is teal.",
            created_at=datetime(2026, 11, 8, 12, 1, tzinfo=timezone.utc),
        )
        conversations.save(replacement_original)
        replacement = reviewer.propose(
            session_id=before["session_id"],
            message_ids=(replacement_original.id,),
            content="The synthetic sensor is teal.",
            created_at=replacement_original.created_at,
        )
        reviewer.link_correction(
            replacement.candidate_id, before["candidate_id"],
            approved_by=before["owner"],
        )
        before["replacement_id"] = replacement.candidate_id
        before["replacement_original"] = replacement_original
        return before
    finally:
        candidates.close()
        conversations.close()


def test_reviewed_correction_prepared_before_restart_is_atomic_and_persistent(tmp_path):
    from sofia.core.memory.system import MemorySystem

    before = _prepare_reviewed_correction(tmp_path)
    identity, personality, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        assert identity == before["identity"]
        assert personality == before["personality"]
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert candidates.status(before["replacement_id"]) is CandidateStatus.PROPOSED
        reviewer.promote(before["replacement_id"], approved_by=before["owner"])
        assert candidates.status(before["candidate_id"]) is CandidateStatus.REVOKED
        assert candidates.status(before["replacement_id"]) is CandidateStatus.PROMOTED
    finally:
        candidates.close()
        conversations.close()

    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        assert candidates.status(before["candidate_id"]) is CandidateStatus.REVOKED
        assert candidates.status(before["replacement_id"]) is CandidateStatus.PROMOTED
        assert [
            item.id for item in MemorySystem(candidates).recall_relevant(
                "synthetic sensor", principal=before["owner"],
            )
        ] == [str(before["replacement_id"])]
    finally:
        candidates.close()
        conversations.close()


@pytest.mark.parametrize("tamper", ("original", "audience"))
def test_promoted_memory_recall_refused_after_restart_when_original_changes(
    tmp_path, tamper,
):
    from sofia.core.memory.system import MemorySystem

    before = _seed(tmp_path)
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        reviewer.promote(before["candidate_id"], approved_by=before["owner"])
        assert candidates.is_recall_eligible(before["candidate_id"])
    finally:
        candidates.close()
        conversations.close()

    with sqlite3.connect(before["state"]) as database:
        if tamper == "original":
            database.execute(
                "UPDATE conversation_messages SET content=? WHERE id=?",
                ("edited original after approval", before["message"].id),
            )
        else:
            database.execute(
                "UPDATE social_session_principal SET audience_id=? WHERE session_id=?",
                ("private:other-device", before["session_id"]),
            )
    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert not candidates.is_recall_eligible(before["candidate_id"])
        assert MemorySystem(candidates).recall_relevant(
            "synthetic sensor", principal=before["owner"],
        ) == ()
    finally:
        candidates.close()
        conversations.close()


def test_interrupted_identity_and_personality_file_replacement_preserves_prior_bytes(
    tmp_path, monkeypatch,
):
    from sofia.core.identity.model import SofiaIdentity
    from sofia.platform.state import atomic_file

    before = _seed(tmp_path)
    identity_path = tmp_path / "identity.json"
    personality_path = tmp_path / "personality.json"
    identity_bytes = identity_path.read_bytes()
    personality_bytes = personality_path.read_bytes()

    def deny_replace(_source, _destination):
        raise PermissionError("synthetic interrupted atomic replacement")

    with monkeypatch.context() as patch:
        patch.setattr(atomic_file.os, "replace", deny_replace)
        patch.setattr(atomic_file.time, "sleep", lambda _seconds: None)
        with pytest.raises(IdentityStoreError):
            IdentityStore(identity_path).save(
                SofiaIdentity(name="Unauthorized replacement",
                              instance_id=before["identity"].instance_id),
            )
        with pytest.raises(PersonalityStoreError):
            PersonalityStore(personality_path).save(
                PersonalityProfile(name="Unauthorized replacement"),
            )

    assert identity_path.read_bytes() == identity_bytes
    assert personality_path.read_bytes() == personality_bytes
    assert not list(tmp_path.glob(".identity.json.*.tmp"))
    assert not list(tmp_path.glob(".personality.json.*.tmp"))
    assert IdentityStore(
        identity_path, bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING
    ).load() == before["identity"]
    assert PersonalityStore(personality_path).load() == before["personality"]


def test_correction_second_sql_update_failure_rolls_back_both_states(tmp_path):
    """A mid-transaction abort cannot leave both facts revoked/promoted."""
    before = _prepare_reviewed_correction(tmp_path)
    with sqlite3.connect(before["state"]) as database:
        database.execute(
            "CREATE TRIGGER deny_synthetic_correction "
            "BEFORE UPDATE OF status ON memory_candidate "
            "WHEN NEW.candidate_id='" + str(before["replacement_id"]) + "' "
            "AND NEW.status='promoted' "
            "BEGIN SELECT RAISE(ABORT, 'synthetic correction write failure'); END"
        )
    _, _, conversations, candidates, reviewer = _reopen(tmp_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="synthetic correction"):
            reviewer.promote(
                before["replacement_id"], approved_by=before["owner"],
            )
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert candidates.status(before["replacement_id"]) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()

    _, _, conversations, candidates, _ = _reopen(tmp_path)
    try:
        assert candidates.status(before["candidate_id"]) is CandidateStatus.PROMOTED
        assert candidates.status(before["replacement_id"]) is CandidateStatus.PROPOSED
    finally:
        candidates.close()
        conversations.close()


def test_legacy_without_review_attestation_is_currently_recall_eligible(tmp_path):
    """CHARACTERIZATION ONLY: existing legacy exception is a policy blocker."""
    from sofia.core.memory.originals import SourceMessage
    from sofia.core.memory.provenance import MemoryCandidate
    from sofia.core.memory.system import MemorySystem

    before = _seed(tmp_path)
    candidates = DurableMemoryCandidateStore(before["state"])
    try:
        legacy = MemoryCandidate(
            candidate_id=uuid4(),
            content="Legacy synthetic unattested violet sensor",
            sources=(SourceMessage(
                message_id="legacy:not-in-originals",
                session_id="legacy:no-bound-session",
                role="user",
                content="historic synthetic text",
                created_at=before["message"].created_at,
                position=0,
            ),),
            created_at=before["message"].created_at,
            principal_id=before["owner"].principal_id,
            audience_id=before["owner"].audience_id,
        )
        candidates.propose(legacy)
        # The low-level compatibility method is intentionally not an owner
        # approval path. This characterizes current behavior, not a policy OK.
        candidates.promote(legacy.candidate_id)
        assert candidates.is_recall_eligible(legacy.candidate_id)
        assert [
            record.id for record in MemorySystem(candidates).recall_relevant(
                "unattested violet", principal=before["owner"],
            )
        ] == [str(legacy.candidate_id)]
    finally:
        candidates.close()
