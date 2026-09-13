from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


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


@pytest.fixture
def personality_path(tmp_path: Path) -> Path:
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


@pytest.fixture
def application(
    personality_path: Path,
) -> SofiaApplication:
    configuration = SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
    )

    return SofiaApplication(configuration)


def test_conversation_can_submit_request(
    application: SofiaApplication,
):
    application.start()

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        ),
    )

    response = application.runtime.respond(request)

    assert response is not None

    application.shutdown()