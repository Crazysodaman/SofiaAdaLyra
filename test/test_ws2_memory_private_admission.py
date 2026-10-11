"""Deferred Phase 06 privacy-first automatic memory admission contracts.

Synthetic messages only. No credentials, production user data, live services,
tests or CI are used during authoring.
"""
from datetime import datetime, timezone

import pytest

from sofia.application.conversation_learning import ConversationLearningCoordinator
from sofia.application.memory_review import MemoryReviewService
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.conversation.store import ConversationStore
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.social.principals import local_sparks_principal
from sofia.social.store import SocialSessionStore
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


@pytest.mark.parametrize("text", (
    "Remember that my password is SYNTHETIC_NOT_REAL",
    "My API key is SYNTHETIC_NOT_REAL",
    "I prefer password abc123 as my login password",
    "Please remember that my seed phrase is all fake words",
    "My bank account number is SYNTHETIC_NOT_REAL",
    "My PIN is SYNTHETIC_NOT_REAL",
    "Remember that my OTP is SYNTHETIC_NOT_REAL",
    "Remember that my recovery codes are FAKE-ONLY",
    "My social security number is SYNTHETIC_NOT_REAL",
    "Remember that my client secret is SYNTHETIC_NOT_REAL",
))
def test_secret_or_credential_message_does_not_auto_propose(text):
    accepted, reason = ConversationLearningCoordinator._is_learnable(text)
    assert accepted is False
    assert reason == "private credential or identity data is not auto-proposed"


@pytest.mark.parametrize("text", (
    "Remember that I prefer quieter trains",
    "I prefer blue locomotives",
    "Actually, I now prefer the freight locomotives",
    "My favorite model railroad is HO scale",
))
def test_ordinary_preferences_still_propose_for_independent_review(text):
    assert ConversationLearningCoordinator._is_learnable(text)[0] is True


def test_sensitive_original_remains_in_source_but_creates_no_memory_candidate(
    tmp_path,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    source = ConversationStore(state)
    candidates = DurableMemoryCandidateStore(state)
    social = SocialSessionStore(state)
    session = source.create_session()
    principal = local_sparks_principal()
    social.bind(session_id=session.id, principal=principal)
    review = MemoryReviewService(
        conversation_store=source, candidate_store=candidates,
        state_path=state,
    )
    learning = ConversationLearningCoordinator(review)
    message = ConversationMessage(
        id="original:private:1", session_id=session.id,
        role=ConversationRole.USER,
        content="Remember that my recovery code is SYNTHETIC_NOT_REAL",
        created_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    try:
        source.save(message)
        outcome = learning.observe_user_message(
            message=message, principal=principal,
        )
        assert outcome.proposed is False
        assert outcome.candidate_id is None
        assert candidates.list_ids() == ()
        assert source.list_messages(session.id) == (message,)
    finally:
        candidates.close()
        source.close()
