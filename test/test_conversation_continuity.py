from pathlib import Path

import pytest

from sofia.application import SofiaApplication, SofiaApplicationError
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


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


def create_configuration(
    tmp_path: Path,
    state_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(
            create_personality(tmp_path)
        ),
        avatar_path=str(AVATAR_PATH),
        state_path=str(state_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def create_application(
    tmp_path: Path,
    state_path: Path,
) -> SofiaApplication:
    return SofiaApplication(
        create_configuration(
            tmp_path,
            state_path,
        )
    )


def test_application_can_explicitly_resume_persisted_conversation(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    application = create_application(
        tmp_path,
        state_path,
    )

    application.start()

    original_session = (
        application.conversation.session
    )

    assert original_session is not None

    application.conversation.respond(
        "Continuity marker: ALPHA-7."
    )

    original_messages = (
        application.conversation.messages()
    )

    assert len(original_messages) == 2

    session_id = original_session.id

    application.shutdown()

    resumed_application = create_application(
        tmp_path,
        state_path,
    )

    resumed_application.start(
        session_id=session_id,
    )

    resumed_session = (
        resumed_application.conversation.session
    )

    assert resumed_session is not None
    assert resumed_session.id == session_id

    resumed_messages = (
        resumed_application.conversation.messages()
    )

    assert resumed_messages == original_messages

    resumed_application.shutdown()


def test_resumed_conversation_continues_same_session(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    application = create_application(
        tmp_path,
        state_path,
    )

    application.start()

    original_session = (
        application.conversation.session
    )

    assert original_session is not None

    application.conversation.respond(
        "First continuity message."
    )

    session_id = original_session.id

    application.shutdown()

    resumed_application = create_application(
        tmp_path,
        state_path,
    )

    resumed_application.start(
        session_id=session_id,
    )

    resumed_application.conversation.respond(
        "Second continuity message."
    )

    messages = (
        resumed_application.conversation.messages()
    )

    assert len(messages) == 4

    assert messages[0].content == (
        "First continuity message."
    )

    assert messages[2].content == (
        "Second continuity message."
    )

    assert all(
        message.session_id == session_id
        for message in messages
    )

    resumed_application.shutdown()


def test_start_without_session_id_creates_new_session(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    first_application = create_application(
        tmp_path,
        state_path,
    )

    first_application.start()

    first_session = (
        first_application.conversation.session
    )

    assert first_session is not None

    first_application.conversation.respond(
        "This belongs to the first session."
    )

    first_session_id = first_session.id

    first_application.shutdown()

    second_application = create_application(
        tmp_path,
        state_path,
    )

    second_application.start()

    second_session = (
        second_application.conversation.session
    )

    assert second_session is not None
    assert second_session.id != first_session_id
    assert second_application.conversation.messages() == ()

    second_application.shutdown()


def test_missing_session_cannot_be_resumed(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    application = create_application(
        tmp_path,
        state_path,
    )

    with pytest.raises(SofiaApplicationError):
        application.start(
            session_id="does-not-exist",
        )

    assert application.conversation.session is None


def test_empty_session_id_is_rejected(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    application = create_application(
        tmp_path,
        state_path,
    )

    with pytest.raises(SofiaApplicationError):
        application.start(
            session_id="   ",
        )

    assert application.conversation.session is None


def test_non_string_session_id_is_rejected(
    tmp_path: Path,
):
    state_path = tmp_path / "sofia.db"

    application = create_application(
        tmp_path,
        state_path,
    )

    with pytest.raises(SofiaApplicationError):
        application.start(
            session_id=123,
        )

    assert application.conversation.session is None