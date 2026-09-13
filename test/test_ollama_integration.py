import os
from pathlib import Path

import pytest

from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
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

OLLAMA_MODEL = os.getenv(
    "SOFIA_OLLAMA_MODEL",
    "qwen3:14b",
)


@pytest.mark.integration
def test_real_ollama_cognitive_path(tmp_path):
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
                "curious",
                "direct"
            ],
            "communication_style":
                "Clear, direct, and analytical."
        }
        """,
        encoding="utf-8",
    )

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
    )

    runtime = compose(configuration)

    assert runtime is not None
    assert runtime.cognitive_system is not None

    assert isinstance(
        runtime.cognitive_system.engine,
        LLMCognitiveEngine,
    )

    assert isinstance(
        runtime.cognitive_system.engine.provider,
        OllamaProvider,
    )

    runtime.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "Reply with exactly: "
                    "Ollama integration is operational."
                ),
            ),
        )
    )

    response = runtime.respond(request)

    assert response is not None
    assert response.content
    assert "Ollama integration is operational." in response.content

    runtime.shutdown()


@pytest.mark.integration
def test_real_ollama_receives_sofia_identity_context(tmp_path):
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
                "Answer precisely and concisely."
        }
        """,
        encoding="utf-8",
    )

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
    )

    runtime = compose(configuration)

    assert isinstance(
        runtime.cognitive_system.engine,
        LLMCognitiveEngine,
    )

    runtime.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "What is your name? "
                    "Use the identity information provided to you. "
                    "Respond with only the exact configured name."
                ),
            ),
        )
    )

    response = runtime.respond(request)

    assert response.content.strip() == "Sofía Ada Lyra"

    runtime.shutdown()


@pytest.mark.integration
def test_real_ollama_receives_sofia_instance_identity(
    tmp_path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        """
        {
            "name": "Sofía Ada Lyra",
            "instance_id": "12345678-1234-5678-1234-567812345678"
        }
        """,
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
                "Answer precisely and concisely."
        }
        """,
        encoding="utf-8",
    )

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
    )

    runtime = compose(configuration)

    runtime.start()

    provider = runtime.cognitive_system.engine.provider

    assert isinstance(
        provider,
        OllamaProvider,
    )

    original_respond = provider.respond

    def inspect_request(
        provider_request: CognitiveRequest,
    ):
        print(
            "\n===== REQUEST SENT TO OLLAMA PROVIDER ====="
        )

        for index, message in enumerate(
            provider_request.messages
        ):
            print(
                f"\n--- MESSAGE {index} "
                f"({message.role.value}) ---"
            )
            print(message.content)

        print(
            "\n===== END REQUEST SENT TO OLLAMA PROVIDER =====\n"
        )

        return original_respond(
            provider_request
        )

    provider.respond = inspect_request

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=(
                    "What is your instance ID? "
                    "Respond with only this exact value: "
                    "12345678-1234-5678-1234-567812345678"
                ),
            ),
        )
    )

    response = runtime.respond(request)

    assert (
        response.content.strip()
        == "12345678-1234-5678-1234-567812345678"
    )

    runtime.shutdown()