"""Synthetic full SofiaApplication-to-memory V1 composition, no live Ollama.

Team 2's unmocked Ollama probe can import the same test-only hook while
providing its own genuine provider. This regression does not prove inference.
"""
from datetime import datetime, timezone

import pytest

from sofia.core.memory.provenance import CandidateStatus
from sofia.core.social.principals import local_sparks_principal
from test.core_team3_policy_fixture import (
    attach_disposable_memory_policy_v1,
    create_disposable_core_application,
)


def test_v1_disposable_application_wiring_survives_restart(tmp_path):
    owner = local_sparks_principal()
    first = create_disposable_core_application(tmp_path)
    first_policy = attach_disposable_memory_policy_v1(
        first, disposable_root=tmp_path, approved_by=owner,
    )
    first.start()
    session_id = first.conversation.session.id
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

    second = create_disposable_core_application(tmp_path)
    second_policy = attach_disposable_memory_policy_v1(
        second, disposable_root=tmp_path, approved_by=owner,
        expected_version=1,
    )
    second.start(session_id=session_id)
    try:
        assert second._runtime.identity == original_identity
        assert second._runtime.personality == original_personality
        assert second.conversation.session.id == session_id
        assert second_policy.allows(candidate.candidate_id)
        assert [x.id for x in second._runtime.memory_system.recall_relevant(
            "violet sensor", principal=owner,
        )] == [str(candidate.candidate_id)]
    finally:
        second.shutdown()


def test_v1_reviewed_correction_reaches_application_memory_after_two_restarts(tmp_path):
    """Actual application memory path; provider remains a synthetic test model."""
    owner = local_sparks_principal()
    first = create_disposable_core_application(tmp_path)
    attach_disposable_memory_policy_v1(
        first, disposable_root=tmp_path, approved_by=owner,
    )
    first.start()
    session_id = first.conversation.session.id
    try:
        first.conversation.respond(
            "Remember that the synthetic calibration marker is sapphire.",
            principal=owner,
        )
        original = next(
            item for item in reversed(first.conversation.messages())
            if item.role.value == "user"
        )
        earlier = first.memory_review.propose(
            session_id=session_id,
            message_ids=(original.id,),
            content="The synthetic calibration marker is sapphire.",
            created_at=original.created_at,
        )
        first.memory_review.promote(
            earlier.candidate_id, approved_by=owner,
        )
        assert [record.id for record in first._runtime.memory_system.recall_relevant(
            "synthetic calibration marker", principal=owner,
        )] == [str(earlier.candidate_id)]

        first.conversation.respond(
            "Correction: the synthetic calibration marker is amber now.",
            principal=owner,
        )
        correction_source = next(
            item for item in reversed(first.conversation.messages())
            if item.role.value == "user"
        )
        replacement = first.memory_review.propose(
            session_id=session_id,
            message_ids=(correction_source.id,),
            content="The synthetic calibration marker is amber.",
            created_at=correction_source.created_at,
        )
        first.memory_review.link_correction(
            replacement.candidate_id, earlier.candidate_id,
            approved_by=owner,
        )
        assert first.memory_review.status(replacement.candidate_id) is CandidateStatus.PROPOSED
    finally:
        first.shutdown()

    second = create_disposable_core_application(tmp_path)
    attach_disposable_memory_policy_v1(
        second, disposable_root=tmp_path, approved_by=owner,
        expected_version=1,
    )
    second.start(session_id=session_id)
    try:
        assert second.memory_review.status(earlier.candidate_id) is CandidateStatus.PROMOTED
        assert second.memory_review.status(replacement.candidate_id) is CandidateStatus.PROPOSED
        second.memory_review.promote(
            replacement.candidate_id, approved_by=owner,
        )
        assert second.memory_review.status(earlier.candidate_id) is CandidateStatus.REVOKED
        assert second.memory_review.status(replacement.candidate_id) is CandidateStatus.PROMOTED
        assert [record.id for record in second._runtime.memory_system.recall_relevant(
            "synthetic calibration marker", principal=owner,
        )] == [str(replacement.candidate_id)]
    finally:
        second.shutdown()

    third = create_disposable_core_application(tmp_path)
    attach_disposable_memory_policy_v1(
        third, disposable_root=tmp_path, approved_by=owner,
        expected_version=1,
    )
    third.start(session_id=session_id)
    try:
        memories = third._runtime.memory_system.recall_relevant(
            "synthetic calibration marker", principal=owner,
        )
        assert [record.id for record in memories] == [str(replacement.candidate_id)]
        assert "amber" in memories[0].content
        assert all("sapphire" not in record.content for record in memories)
    finally:
        third.shutdown()


@pytest.mark.parametrize(
    "missing_authority",
    ("identity.json", "constitution.sha256", "personality.json"),
)
def test_disposable_application_restart_never_regenerates_authority(
    tmp_path, missing_authority,
):
    """If prior authority is missing, refuse restart rather than bootstrap."""
    app = create_disposable_core_application(tmp_path)
    app.start()
    try:
        assert app._runtime.identity is not None
        assert app._runtime.personality is not None
    finally:
        app.shutdown()
    (tmp_path / missing_authority).unlink()
    with pytest.raises(FileNotFoundError, match="complete existing authority"):
        create_disposable_core_application(tmp_path)
    assert not (tmp_path / missing_authority).exists()
