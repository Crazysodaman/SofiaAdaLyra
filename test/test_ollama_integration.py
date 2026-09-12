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
from sofia.cognition.system import CognitiveSystem
from sofia.composition.root import compose
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

OLLAMA_MODEL = os.getenv(
    "SOFIA_OLLAMA_MODEL",
    "qwen3:14b",
)


@pytest.mark.integration
def test_real_ollama_cognitive_path():
    if not IDENTITY_PATH.exists():
        pytest.fail(
            f"Required identity file does not exist: {IDENTITY_PATH}"
        )

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
    )

    runtime = compose(configuration)

    assert runtime.state is RuntimeState.CREATED

    assert isinstance(
        runtime.cognitive_system,
        CognitiveSystem,
    )

    assert isinstance(
        runtime.cognitive_system.engine,
        LLMCognitiveEngine,
    )

    assert isinstance(
        runtime.cognitive_system.engine.provider,
        OllamaProvider,
    )

    runtime.start()

    assert runtime.state is RuntimeState.READY
    assert runtime.constitution is not None
    assert runtime.identity is not None

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

    assert response.content
    assert "Ollama integration is operational." in response.content

    runtime.shutdown()

    assert runtime.state is RuntimeState.STOPPED