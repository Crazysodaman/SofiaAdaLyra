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

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
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
                    "Respond with exactly this sentence: "
                    "Ollama integration is operational."
                ),
            ),
        ),
    )

    response = runtime.respond(request)

    assert response is not None
    assert response.content
    assert "Ollama integration is operational." in response.content

    runtime.shutdown()