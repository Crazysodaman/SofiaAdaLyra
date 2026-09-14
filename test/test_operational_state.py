from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.operational.model import OperationalState


def create_state() -> OperationalState:
    return OperationalState(
        runtime_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        lifecycle_state="READY",
        application_name="sofia-ada-lyra",
        application_version="0.1.0",
        provider="ollama",
        model="qwen3:14b",
    )


def test_operational_state_is_constructed():
    state = create_state()

    assert state.lifecycle_state == "READY"
    assert state.provider == "ollama"
    assert state.model == "qwen3:14b"


def test_operational_state_is_immutable():
    state = create_state()

    with pytest.raises(AttributeError):
        state.lifecycle_state = "STOPPED"


def test_runtime_id_must_be_uuid():
    with pytest.raises(TypeError):
        OperationalState(
            runtime_id="runtime",
            started_at=datetime.now(timezone.utc),
            lifecycle_state="READY",
            application_name="sofia-ada-lyra",
            application_version="0.1.0",
            provider="ollama",
            model="qwen3:14b",
        )


def test_started_at_must_be_timezone_aware():
    with pytest.raises(ValueError):
        OperationalState(
            runtime_id=uuid4(),
            started_at=datetime.now(),
            lifecycle_state="READY",
            application_name="sofia-ada-lyra",
            application_version="0.1.0",
            provider="ollama",
            model="qwen3:14b",
        )


def test_lifecycle_state_must_not_be_empty():
    with pytest.raises(ValueError):
        OperationalState(
            runtime_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            lifecycle_state="",
            application_name="sofia-ada-lyra",
            application_version="0.1.0",
            provider="ollama",
            model="qwen3:14b",
        )