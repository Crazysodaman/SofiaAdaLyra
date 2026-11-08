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
