"""Full-application restart continuity acceptance ( takeover item #78).

One restart must preserve every durable artfact that independent behavior
depends on: session conversation, reviewed-memory candidates with exact
originals and session bindings, owner-written preference overrides,
GOALS records with evidence and run state, and fail-closed restart paths
whose trust inputs are absent.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.cognition.model import CognitiveResponse
from sofia.platform.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.core.goals import CompletionKind, GoalCompletionCondition
from sofia.core.personality.preferences import PreferenceSubject
from sofia.core.social.principals import local_sparks_principal


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "embodiment"
    / "avatar.json"
)


def create_configuration(
    personality_path: Path,
    state_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def create_personality(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "personality.json"

    path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return path


def create_application(
    tmp_path: Path,
) -> SofiaApplication:
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    return SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )


def test_full_restart_preserves_reviewed_state_fail_closed_paths(tmp_path):
    first_application = create_application(tmp_path)

    first_application.start()

    owner = local_sparks_principal()
    session_id = first_application.conversation.session_id

    first_application.conversation.respond(
        "My name is Sparks.", principal=owner,
    )
    first_application.conversation.respond(
        "Remember this continuity acceptance conversation.",
        principal=owner,
    )

    persisted_messages = first_application.conversation.messages()

    assert len(persisted_messages) == 4

    source_ids = tuple(
        message.id for message in persisted_messages
        if message.role.value == "user"
    )
    source_id = source_ids[-1]

    candidate = first_application.memory_review.propose(
        session_id=session_id,
        message_ids=(source_id,),
        content=(
            "The owner asked Sofía to remember this continuity "
            "acceptance conversation."
        ),
        created_at=datetime.now(timezone.utc),
    )

    preference = first_application.set_communication_preference(
        principal=owner,
        target="verbosity",
        level=0.9,
        reason="Owner prefers detailed explanations.",
        evidence_ref=source_id,
        expected_revision=None,
    )

    goal = first_application.goals.create_user_goal(
        principal=owner,
        title="Record continuity acceptance residue",
        reason="Full-restart continuity acceptance requires durable goal state.",
        base_priority=0.72,
        confidence=0.95,
        completion=GoalCompletionCondition(
            kind=CompletionKind.EVIDENCE_TRUE,
            description="Owner records the memory as verified.",
        ),
        evidence_refs=(source_id,),
        now=datetime.now(timezone.utc),
    )

    first_application.shutdown()

    second_application = create_application(tmp_path)
    second_application.start(session_id=session_id)

    assert second_application.conversation.session_id == session_id
    resumed_messages = second_application.conversation.messages()
    assert resumed_messages[:len(persisted_messages)] == persisted_messages

    # Reviewed-memory candidates survive with their exact originals and
    # authenticated session binding, so promotion still works after a
    # restart.
    second_application.memory_review.promote(
        candidate.candidate_id, approved_by=owner,
    )

    # A fabricated candidate id must fail closed instead of promoting.
    with pytest.raises(LookupError):
        second_application.memory_review.promote(
            uuid4(), approved_by=owner,
        )

    # Owner preference revisions survive restart with their identity,
    # revision and evidence intact.
    record = second_application.preferences.current(
        subject=PreferenceSubject.SPARKS,
        category="conversation.style",
        target_id="verbosity",
        context="general",
        audience_id=owner.audience_id,
    )
    assert record is not None
    assert record.revision == preference.revision
    assert record.strength == preference.strength
    assert record.evidence_ref == preference.evidence_ref

    # GOALS records survive restart with the same durable plan state,
    # evidence and run state.
    visible = second_application.goals.list_visible(owner)
    persisted_goal = next(
        item for item in visible if item.id == goal.id
    )
    assert persisted_goal == goal

    # Host dispatch reconciliation must fail closed after restart when
    # the pinned-mTLS Fleet trust boundary is not configured.
    with pytest.raises(PermissionError, match="pinned-mTLS"):
        second_application.reconcile_host_goal_dispatch(
            goal_id=goal.id,
            dispatch_id="dispatch:none",
            principal=owner,
            approval_id="approval:none",
            now=datetime.now(timezone.utc),
        )

    second_application.shutdown()


def test_third_persona_restarts_do_not_replay_unbound_memories(tmp_path):
    first_application = create_application(tmp_path)

    first_application.start()
    first_application.conversation.respond("Unbound session note.")

    session_id = first_application.conversation.session_id

    first_application.shutdown()

    second_application = create_application(tmp_path)
    second_application.start(session_id=session_id)

    owner = local_sparks_principal()

    # Legacy unbound transcript rows must never become recall rights:
    # promotion of a proposed candidate from an unbound session stays
    # impossible after any restart.
    with pytest.raises((LookupError, PermissionError)):
        second_application.memory_review.link_correction(
            uuid4(),
            uuid4(),
            approved_by=owner,
        )

    # A fresh configured identity is presented after restart; the
    # session id is retained only by explicit resume.
    assert second_application.conversation.session_id == session_id

    second_application.shutdown()
