"""Synthetic full SofiaApplication-to-memory V1 composition, no live Ollama.

Team 2's unmocked Ollama probe can import the same test-only hook while
providing its own genuine provider. This regression does not prove inference.
"""
from datetime import datetime, timezone

from sofia.core.memory.provenance import CandidateStatus
from sofia.core.social.principals import local_sparks_principal
from test.core_team3_policy_fixture import attach_disposable_memory_policy_v1
from test.test_application_restart_continuity import create_application


def test_v1_disposable_application_wiring_survives_restart(tmp_path):
    owner = local_sparks_principal()
    first = create_application(tmp_path)
    first_policy = attach_disposable_memory_policy_v1(
        first, disposable_root=tmp_path, approved_by=owner,
    )
    first.start()
    session_id = first.conversation.session_id
    try:
        first.conversation.respond(
            "Remember that the synthetic violet sensor is connected.",
            principal=owner,
        )
        user_messages = tuple(
            message for message in first.conversation.messages()
            if message.role.value == "user"
        )
        assert user_messages
        source = user_messages[-1]
        candidate = first.memory_review.propose(
            session_id=session_id, message_ids=(source.id,),
            content="Synthetic violet sensor is connected.",
            created_at=datetime.now(timezone.utc),
        )
        memory = first._runtime.memory_system
        # Characterize only the historical low-level promotion path; V1
        # must quarantine it until authenticated review of real originals.
        memory.candidate_store.promote(candidate.candidate_id)
        assert memory.candidate_store.status(candidate.candidate_id) is CandidateStatus.PROMOTED
        assert first_policy.allows(candidate.candidate_id) is False
        assert memory.recall_relevant("violet sensor", principal=owner) == ()

        receipt_digest = first.memory_review.re_review_legacy_promoted(
            candidate.candidate_id, approved_by=owner,
        )
        assert len(receipt_digest) == 64
        assert [x.id for x in memory.recall_relevant(
            "violet sensor", principal=owner,
        )] == [str(candidate.candidate_id)]
        original_identity = first._runtime.identity
        original_personality = first._runtime.personality
    finally:
        first.shutdown()

    second = create_application(tmp_path)
    second_policy = attach_disposable_memory_policy_v1(
        second, disposable_root=tmp_path, approved_by=owner,
        expected_version=1,
    )
    second.start(session_id=session_id)
    try:
        assert second._runtime.identity == original_identity
        assert second._runtime.personality == original_personality
        assert second.conversation.session_id == session_id
        assert second_policy.allows(candidate.candidate_id)
        assert [x.id for x in second._runtime.memory_system.recall_relevant(
            "violet sensor", principal=owner,
        )] == [str(candidate.candidate_id)]
    finally:
        second.shutdown()
