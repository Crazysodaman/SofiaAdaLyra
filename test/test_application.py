from pathlib import Path

import pytest

from sofia.application import SofiaApplication, SofiaApplicationError
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.runtime.model import RuntimeState


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


def create_configuration(
    personality_path: Path,
) -> SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=str(CONSTITUTION_PATH),
        constitution_hash_path=str(HASH_PATH),
        identity_path=str(IDENTITY_PATH),
        personality_path=str(personality_path),
        avatar_path=str(AVATAR_PATH),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
    )


def test_new_application_is_not_started(
    personality_path: Path,
):
    application = SofiaApplication(
        create_configuration(personality_path)
    )

    assert application.runtime.state is RuntimeState.CREATED


def test_start_starts_runtime(
    personality_path: Path,
):
    application = SofiaApplication(
        create_configuration(personality_path)
    )

    application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_stops_runtime(
    personality_path: Path,
):
    application = SofiaApplication(
        create_configuration(personality_path)
    )

    application.start()
    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED


def test_start_twice_is_rejected(
    personality_path: Path,
):
    application = SofiaApplication(
        create_configuration(personality_path)
    )

    application.start()

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_before_start_is_rejected(
    personality_path: Path,
):
    application = SofiaApplication(
        create_configuration(personality_path)
    )

    with pytest.raises(SofiaApplicationError):
        application.shutdown()

    assert application.runtime.state is RuntimeState.CREATED


def test_start_failure_is_exposed_as_application_error(
    tmp_path: Path,
):
    configuration = SofiaConfiguration(
        constitution_path=str(tmp_path / "missing.md"),
        constitution_hash_path=str(tmp_path / "missing.sha256"),
        identity_path=str(tmp_path / "missing.json"),
        personality_path=str(tmp_path / "missing-personality.json"),
        avatar_path=str(tmp_path / "missing-avatar.json"),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
    )

    application = SofiaApplication(configuration)

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.FAILED
