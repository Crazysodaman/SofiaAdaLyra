from pathlib import Path

from sofia.application import SofiaApplication
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.cognition.engine import CognitiveEngine
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.conversation.model import ConversationRole


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


class RecordingContextEngine(CognitiveEngine):
    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.requests.append(request)

        return CognitiveResponse(
            content="Integration response.",
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
    "name": "Sofía Ada Lyra",
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


def test_conversation_request_contains_assembled_sofia_context(
    tmp_path: Path,
) -> None:
    application = SofiaApplication(
        create_configuration(
            create_personality(tmp_path),
            tmp_path / "sofia.db",
        )
    )

    engine = RecordingContextEngine()

    application.runtime.cognitive_system.engine = engine

    application.start()

    response = application.conversation.respond(
        "Tell me who you are.",
    )

    assert response.content == "Integration response."

    assert len(engine.requests) == 1

    request = engine.requests[0]

    assert request.messages[0].role.value == "system"

    system_context = request.messages[0].content

    assert "Sofía Ada Lyra" in system_context
    assert "IDENTITY" in system_context
    assert "PERSONALITY" in system_context
    assert "CONSTITUTION" in system_context
    assert "EMBODIMENT" in system_context

    assert request.messages[-1].role.value == "user"
    assert request.messages[-1].content == "Tell me who you are."

    messages = application.conversation.messages()

    assert len(messages) == 2
    assert messages[0].role is ConversationRole.USER
    assert messages[1].role is ConversationRole.ASSISTANT

    application.shutdown()