from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.runtime.model import RuntimeState


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


@pytest.fixture
def configuration(tmp_path: Path) -> SofiaConfiguration:
    personality_path = (
        tmp_path
        / "personality.json"
    )

    personality_path.write_text(
        """
{
    "name": "Sofía",
    "traits": [
        "rigorous",
        "analytical",
        "curious",
        "direct"
    ],
    "communication_style": "Clear, direct, and analytical."
}
""".strip(),
        encoding="utf-8",
    )

    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="test",
            model="acceptance",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_full_application_conversation_lifecycle(
    configuration: SofiaConfiguration,
):
    application = SofiaApplication(
        configuration
    )

    application.start()

    assert application.runtime.state is RuntimeState.READY
    assert application.conversation.session_id is not None

    response = application.conversation.respond(
        "Hello, Sofía."
    )

    assert response.content == "Test cognitive response."

    messages = application.conversation.messages()

    assert len(messages) == 2
    assert messages[0].content == "Hello, Sofía."
    assert messages[1].content == "Test cognitive response."

    session_id = application.conversation.session_id

    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED

    resumed_application = SofiaApplication(
        configuration
    )

    resumed_application.start(
        session_id=session_id
    )

    resumed_messages = (
        resumed_application.conversation.messages()
    )

    assert len(resumed_messages) == 2
    assert resumed_messages[0].content == "Hello, Sofía."
    assert (
        resumed_messages[1].content
        == "Test cognitive response."
    )

    resumed_application.shutdown()


def test_application_creates_new_session_when_not_resuming(
    configuration: SofiaConfiguration,
):
    first_application = SofiaApplication(
        configuration
    )

    first_application.start()

    first_session_id = (
        first_application.conversation.session_id
    )

    first_application.shutdown()

    second_application = SofiaApplication(
        configuration
    )

    second_application.start()

    second_session_id = (
        second_application.conversation.session_id
    )

    assert first_session_id is not None
    assert second_session_id is not None
    assert second_session_id != first_session_id

    second_application.shutdown()