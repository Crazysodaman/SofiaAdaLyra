from pathlib import Path

import pytest

from sofia.application import (
    ConversationService,
    SofiaApplication,
)
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.conversation.model import (
    ConversationRole,
)


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


def test_conversation_service_is_application_boundary(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    assert isinstance(
        application.conversation,
        ConversationService,
    )

    assert application.conversation.session is None
    assert application.conversation.session_id is None

    application.start()

    assert application.conversation.session is not None
    assert application.conversation.session_id is not None

    application.shutdown()


def test_conversation_service_creates_session_on_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    session = application.conversation.session

    assert session is not None
    assert session.id == application.conversation.session_id

    application.shutdown()


def test_conversation_service_persists_user_and_assistant_messages(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "Hello, Sofía."
    )

    messages = application.conversation.messages()

    assert response.content == "Test cognitive response."

    assert len(messages) == 2

    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "Hello, Sofía."

    assert messages[1].role is ConversationRole.ASSISTANT
    assert messages[1].content == "Test cognitive response."

    application.shutdown()


def test_conversation_service_preserves_conversation_history(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "First message."
    )

    application.conversation.respond(
        "Second message."
    )

    messages = application.conversation.messages()

    assert len(messages) == 4

    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "First message."

    assert messages[1].role is ConversationRole.ASSISTANT
    assert messages[1].content == "Test cognitive response."

    assert messages[2].role is ConversationRole.USER
    assert messages[2].content == "Second message."

    assert messages[3].role is ConversationRole.ASSISTANT
    assert messages[3].content == "Test cognitive response."

    application.shutdown()


def test_conversation_service_rejects_response_before_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    with pytest.raises(
        RuntimeError,
        match="ConversationService must be started before responding.",
    ):
        application.conversation.respond(
            "Hello, Sofía."
        )


def test_conversation_service_rejects_empty_response(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        ValueError,
        match="ConversationService content must not be empty.",
    ):
        application.conversation.respond("   ")

    application.shutdown()


def test_conversation_service_rejects_non_string_response(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        TypeError,
        match="ConversationService content must be a string.",
    ):
        application.conversation.respond(None)

    application.shutdown()


def test_conversation_service_rejects_second_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    with pytest.raises(
        RuntimeError,
        match="ConversationService already has an active session.",
    ):
        application.conversation.start()

    application.shutdown()