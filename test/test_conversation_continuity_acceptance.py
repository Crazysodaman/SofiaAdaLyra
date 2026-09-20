from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import CognitiveRole
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.filesystem.model import FilesystemResult


PROJECT_ROOT = Path(__file__).parent.parent

CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
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
    return SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )


def test_restart_and_resume_preserves_cognitive_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    first_application = create_application(tmp_path)

    first_application.start()

    session_id = first_application.conversation.session_id

    assert session_id is not None

    first_application.conversation.respond(
        "My name is Sparks."
    )

    first_application.conversation.respond(
        "Remember that this conversation is a continuity test."
    )

    persisted_messages = first_application.conversation.messages()

    assert len(persisted_messages) == 4

    first_application.shutdown()

    second_application = create_application(tmp_path)

    captured_requests = []
    captured_filesystem_results = []

    def capture_request(
        request,
        *,
        filesystem_results: tuple[FilesystemResult, ...] = (),
    ):
        captured_requests.append(request)
        captured_filesystem_results.append(
            filesystem_results
        )

        return type(
            "CapturedResponse",
            (),
            {
                "content": "Continuity confirmed."
            },
        )()

    monkeypatch.setattr(
        second_application.runtime,
        "respond",
        capture_request,
    )

    second_application.start(
        session_id=session_id,
    )

    assert second_application.conversation.session_id == session_id

    resumed_messages = second_application.conversation.messages()

    assert len(resumed_messages) == len(persisted_messages) + 1
    assert resumed_messages[:len(persisted_messages)] == persisted_messages
    assert resumed_messages[-1].role.value == "assistant"
    assert resumed_messages[-1].content == "Continuity confirmed."

    response = second_application.conversation.respond(
        "What did I say earlier?"
    )

    assert response.content == "Continuity confirmed."

    assert len(captured_requests) == 2  # Awareness, then user request.
    assert captured_requests[0].messages[0].role is CognitiveRole.SYSTEM
    assert captured_filesystem_results == [(), ()]

    request = captured_requests[1]

    assert len(request.messages) == 6

    assert request.messages[0].role is CognitiveRole.USER
    assert request.messages[0].content == "My name is Sparks."

    assert request.messages[1].role is CognitiveRole.ASSISTANT
    assert request.messages[1].content == "Test cognitive response."

    assert request.messages[2].role is CognitiveRole.USER
    assert (
        request.messages[2].content
        == "Remember that this conversation is a continuity test."
    )

    assert request.messages[3].role is CognitiveRole.ASSISTANT
    assert request.messages[3].content == "Test cognitive response."

    assert request.messages[4].role is CognitiveRole.ASSISTANT
    assert request.messages[4].content == "Continuity confirmed."
    assert request.messages[5].role is CognitiveRole.USER
    assert request.messages[5].content == "What did I say earlier?"

    second_application.shutdown()


def test_new_conversation_after_restart_does_not_reuse_previous_session(
    tmp_path: Path,
):
    first_application = create_application(tmp_path)

    first_application.start()

    first_session_id = first_application.conversation.session_id

    assert first_session_id is not None

    first_application.conversation.respond(
        "This belongs to the first conversation."
    )

    first_application.shutdown()

    second_application = create_application(tmp_path)

    second_application.start()

    second_session_id = second_application.conversation.session_id

    assert second_session_id is not None
    assert second_session_id != first_session_id

    messages = second_application.conversation.messages()

    assert len(messages) == 1  # Fresh session gets only startup awareness.
    assert messages[0].role.value == "assistant"
    assert messages[0].session_id == second_session_id
    assert "This belongs to the first conversation." not in messages[0].content

    second_application.shutdown()


def test_explicit_resume_does_not_create_a_new_session(
    tmp_path: Path,
):
    first_application = create_application(tmp_path)

    first_application.start()

    session_id = first_application.conversation.session_id

    assert session_id is not None

    first_application.conversation.respond(
        "Persistent conversation."
    )

    first_application.shutdown()

    second_application = create_application(tmp_path)

    second_application.start(
        session_id=session_id,
    )

    assert second_application.conversation.session_id == session_id

    messages = second_application.conversation.messages()

    assert len(messages) == 3
    assert messages[0].content == "Persistent conversation."
    assert messages[1].content == "Test cognitive response."
    assert messages[2].role.value == "assistant"
    assert messages[2].session_id == session_id

    second_application.shutdown()


def test_resume_then_shutdown_closes_application_cleanly(
    tmp_path: Path,
):
    first_application = create_application(tmp_path)

    first_application.start()

    session_id = first_application.conversation.session_id

    assert session_id is not None

    first_application.conversation.respond(
        "Lifecycle continuity."
    )

    first_application.shutdown()

    second_application = create_application(tmp_path)

    second_application.start(
        session_id=session_id,
    )

    assert second_application.conversation.session_id == session_id

    second_application.shutdown()
