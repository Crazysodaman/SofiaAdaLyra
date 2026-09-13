from pathlib import Path

import pytest

from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.ollama import OllamaProvider


ROOT = Path(__file__).resolve().parents[1]

CONSTITUTION_PATH = (
    ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)

HASH_PATH = (
    ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)

AVATAR_PATH = (
    ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)

OLLAMA_MODEL = "qwen3:14b"


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
            "traits": [],
            "communication_style": ""
        }
        """,
        encoding="utf-8",
    )

    state_path = tmp_path / "sofia.db"

    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR_PATH,
        state_path=state_path,
        provider=ProviderConfiguration(
            provider="ollama",
            model=OLLAMA_MODEL,
        ),
    )

    provider = OllamaProvider(configuration.provider)

    response = provider.generate(
        "Respond with exactly: OLLAMA_INTEGRATION_OK"
    )

    assert response.content
    assert "OLLAMA_INTEGRATION_OK" in response.content