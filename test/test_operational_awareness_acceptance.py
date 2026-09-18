from pathlib import Path
from uuid import UUID

import pytest

from sofia.application import SofiaApplication
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
            model="test-model",
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


def test_operational_state_is_unknown_before_runtime_start(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    assert application.runtime.state is RuntimeState.CREATED
    assert application.runtime.operational_state is None


def test_operational_state_contains_authoritative_runtime_information(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    state = application.runtime.operational_state

    assert state is not None

    assert isinstance(state.runtime_id, UUID)
    assert state.started_at is not None

    assert state.lifecycle_state == RuntimeState.READY.value

    assert state.application_name == "sofia-ada-lyra"
    assert state.application_version

    assert state.provider == "test"
    assert state.model == "test-model"

    application.shutdown()


def test_runtime_id_changes_after_restart(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    first_runtime_id = application.runtime.runtime_id
    first_started_at = application.runtime.started_at
    first_identity = application.runtime.identity

    assert first_runtime_id is not None
    assert first_started_at is not None
    assert first_identity is not None

    application.shutdown()

    application.start()

    second_runtime_id = application.runtime.runtime_id
    second_started_at = application.runtime.started_at
    second_identity = application.runtime.identity

    assert second_runtime_id is not None
    assert second_started_at is not None
    assert second_identity is not None

    assert second_runtime_id != first_runtime_id
    assert second_started_at != first_started_at
    assert second_identity.instance_id == first_identity.instance_id

    continuity = application.runtime.runtime_continuity

    assert continuity is not None
    assert continuity.restart_observed is True
    assert continuity.previous_runtime_id == first_runtime_id
    assert continuity.previous_started_at == first_started_at

    application.shutdown()


def test_first_runtime_has_no_previous_runtime_evidence(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    continuity = application.runtime.runtime_continuity

    assert continuity is not None
    assert continuity.previous_runtime_id is None
    assert continuity.previous_started_at is None
    assert continuity.restart_observed is None

    application.shutdown()


def test_shutdown_clears_runtime_specific_operational_state(
    tmp_path: Path,
):
    application = create_application(tmp_path)

    application.start()

    assert application.runtime.runtime_id is not None
    assert application.runtime.started_at is not None
    assert application.runtime.operational_state is not None
    assert application.runtime.runtime_continuity is not None

    application.shutdown()

    assert application.runtime.state is RuntimeState.STOPPED
    assert application.runtime.runtime_id is None
    assert application.runtime.started_at is None
    assert application.runtime.operational_state is None
    assert application.runtime.runtime_continuity is None
    assert application.runtime.identity is None


def test_failed_start_does_not_expose_partial_operational_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    application = create_application(tmp_path)

    def fail_load():
        raise RuntimeError("simulated startup failure")

    monkeypatch.setattr(
        application.runtime.constitution_store,
        "load",
        fail_load,
    )

    with pytest.raises(Exception):
        application.start()

    assert application.runtime.state is RuntimeState.FAILED
    assert application.runtime.runtime_id is None
    assert application.runtime.started_at is None
    assert application.runtime.operational_state is None
    assert application.runtime.runtime_continuity is None