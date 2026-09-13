from pathlib import Path

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


CONSTITUTION_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

IDENTITY_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)

AVATAR_PATH = (
    Path(__file__).parent.parent
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


def test_conversation_service_creates_session(
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )

    application.start()

    assert isinstance(
        application.conversation,
        ConversationService,
    )

    assert application.conversation.session is not None
    assert application.conversation.session_id is not None

    application.shutdown()


def test_conversation_service_persists_user_and_assistant_messages(
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )

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
    application = SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )

    application.start()

    application.conversation.respond(
        "First message."
    )

    application.conversation.respond(
        "Second message."
    )

    messages = application.conversation.messages()

    assert len(messages) == 4

    assert messages[0].content == "First message."
    assert messages[1].content == "Test cognitive response."
    assert messages[2].content == "Second message."
    assert messages[3].content == "Test cognitive response."

    application.shutdown()


def test_conversation_service_rejects_response_before_start(
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )

    service = ConversationService(
        runtime=application.runtime,
        conversation_store=application.conversation_store,
    )