from pathlib import Path
import sqlite3

import pytest

from sofia.application import SofiaApplication, SofiaApplicationError
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.run.lifecycle import RunLifecycleState, RunLifecycleStore
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

AVATAR_PATH = (
    PROJECT_ROOT
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


def test_new_application_is_not_started(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    assert application.runtime.state is RuntimeState.CREATED


def test_start_starts_runtime(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_stops_runtime(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()
    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED


def test_start_twice_is_rejected(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.READY


def test_shutdown_before_start_is_rejected(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
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
        state_path=str(tmp_path / "sofia.db"),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=tmp_path,
    )

    application = SofiaApplication(configuration)

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.state is RuntimeState.FAILED


def test_start_opens_disabled_runtime_control_plane(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()

    control = application.runtime.control_plane
    assert control.opened is True
    assert control.run_periodic_gate.policy.enabled is False

    application.shutdown()


def test_shutdown_closes_runtime_control_plane(
    personality_path: Path,
    tmp_path: Path,
):
    application = SofiaApplication(
        create_configuration(
            personality_path,
            tmp_path / "sofia.db",
        )
    )

    application.start()
    control = application.runtime.control_plane

    application.shutdown()

    assert control.opened is False
    with pytest.raises(RuntimeError):
        _ = control.act_outbox



def test_start_records_ready_run_lifecycle(
    personality_path: Path,
    tmp_path: Path,
):
    state = tmp_path / "sofia.db"
    application = SofiaApplication(
        create_configuration(personality_path, state)
    )

    application.start()

    assert application.runtime.control_plane.run_lifecycle_store.current().state is RunLifecycleState.READY
    application.shutdown()
    assert RunLifecycleStore(state).current().state is RunLifecycleState.STOPPED


def test_start_failure_rolls_back_control_plane_and_records_failed(tmp_path: Path):
    state = tmp_path / "sofia.db"
    configuration = SofiaConfiguration(
        constitution_path=str(tmp_path / "missing.md"),
        constitution_hash_path=str(tmp_path / "missing.sha256"),
        identity_path=str(tmp_path / "missing.json"),
        personality_path=str(tmp_path / "missing-personality.json"),
        avatar_path=str(tmp_path / "missing-avatar.json"),
        state_path=str(state),
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=tmp_path,
    )
    application = SofiaApplication(configuration)

    with pytest.raises(SofiaApplicationError):
        application.start()

    assert application.runtime.control_plane.opened is False
    assert RunLifecycleStore(state).current().state is RunLifecycleState.FAILED
