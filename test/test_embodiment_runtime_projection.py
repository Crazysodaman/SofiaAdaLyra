from pathlib import Path

from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProvider
from sofia.composition.root import compose
from sofia.config.model import (
    ProviderConfiguration,
    SofiaConfiguration,
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

AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


class CapturingProvider(LLMProvider):
    """
    Deterministic provider used to capture the exact cognitive
    request presented to the LLM provider boundary.
    """

    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.requests.append(request)

        return CognitiveResponse(
            content="Captured.",
        )


def create_configuration(
    tmp_path,
) -> SofiaConfiguration:
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    personality_path = tmp_path / "personality.json"

    personality_path.write_text(
        """
        {
            "name": "Sofía Ada Lyra",
            "traits": [
                "rigorous",
                "direct"
            ],
            "communication_style":
                "Clear, direct, and analytical."
        }
        """,
        encoding="utf-8",
    )

    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model="test-model",
        ),
        filesystem_root=PROJECT_ROOT,
    )


def test_runtime_projects_canonical_embodiment_to_provider_boundary(
    tmp_path,
):
    configuration = create_configuration(
        tmp_path
    )

    runtime = compose(configuration)

    runtime.start()

    provider = CapturingProvider()

    runtime.cognitive_system.engine = LLMCognitiveEngine(
        configuration=configuration.provider,
        provider=provider,
    )

    runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What are your measurements?",
                ),
            ),
        )
    )

    assert len(provider.requests) == 1

    captured_request = provider.requests[0]

    assert captured_request.messages

    system_message = captured_request.messages[0]

    assert system_message.role is CognitiveRole.SYSTEM

    system_content = system_message.content

    assert "EMBODIMENT" in system_content

    assert "CANONICAL MEASUREMENTS" in system_content

    assert "- height: 67 in" in system_content
    assert "- weight: 135 lb" in system_content
    assert "- bust: 33 in" in system_content
    assert "- underbust: 30 in" in system_content
    assert "- waist: 26 in" in system_content
    assert "- hips: 37 in" in system_content

    assert "Additional features: fox ears, fox tail" in system_content

    assert (
        "Status: CANON: "
        "Sofía Clothing Technical Specification v1.0"
        in system_content
    )

    assert any(
        message.role is CognitiveRole.USER
        and message.content == "What are your measurements?"
        for message in captured_request.messages
    )

    runtime.shutdown()