from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from sofia.application import (
    ConversationService,
    SofiaApplication,
)
from sofia.application.conversation_service import _conversation_tools_relevant
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


def test_conversation_service_can_respond_from_worker_thread(
    tmp_path: Path,
):
    application = create_application(tmp_path)
    application.start()

    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(
            application.conversation.respond,
            "Hello from a worker thread.",
        ).result(timeout=5)

    assert response.content == "Test cognitive response."

    messages = application.conversation.messages()
    assert len(messages) == 2
    assert messages[0].role is ConversationRole.USER
    assert messages[0].content == "Hello from a worker thread."
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
def test_conversation_service_processes_filesystem_authorization(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "you are allowed to check your own files"
    )

    assert response.content == "Test cognitive response."

    assert (
        application.runtime.filesystem_authorization
        is not None
    )

    assert (
        application.runtime.filesystem_inspector.authorized
        is True
    )

    application.shutdown()


def test_conversation_service_processes_filesystem_request(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    application.conversation.respond(
        "you are allowed to check your own files"
    )

    response = application.conversation.respond(
        "read src/sofia/filesystem/model.py"
    )

    assert response.content == "Test cognitive response."

    messages = application.conversation.messages()

    assert messages[-2].content == (
        "read src/sofia/filesystem/model.py"
    )

    assert messages[-1].content == (
        "Test cognitive response."
    )

    application.shutdown()


def test_filesystem_request_without_authorization_remains_denied(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    response = application.conversation.respond(
        "read src/sofia/filesystem/model.py"
    )

    assert response.content == "Test cognitive response."

    assert (
        application.runtime.filesystem_inspector.authorized
        is False
    )

    application.shutdown()

@pytest.mark.parametrize(
    "content",
    (
        "hru",
        "Central timezone",
        "what is the weather today",
        "what are you wearing",
        "I missed you",
    ),
)
def test_conversation_tool_gate_keeps_ordinary_turns_tool_free(content):
    assert _conversation_tools_relevant(content) is False


@pytest.mark.parametrize(
    "content",
    (
        "check current CPU usage",
        "list running services",
        "is Plex running",
        "restart the service",
        "what is the system status",
    ),
)
def test_conversation_tool_gate_allows_operational_turns(content):
    assert _conversation_tools_relevant(content) is True


def test_live_conversation_request_preserves_tool_relevance_gate(tmp_path: Path):
    application = create_application(tmp_path)
    application.start()
    try:
        application.conversation.respond("hru")
        social_request = application.conversation._build_request()
        assert social_request.allow_tools is False

        application.conversation.respond("check current CPU usage")
        operational_request = application.conversation._build_request()
        assert operational_request.allow_tools is True
    finally:
        application.shutdown()

