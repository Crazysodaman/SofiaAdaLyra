from datetime import datetime, timezone

import pytest

from sofia.external import (
    ExternalIntegrationAdapter,
    ExternalObservationState,
    ExternalSystem,
    ExternalSystemObservation,
    ExternalSystemType,
)


class TestExternalAdapter(ExternalIntegrationAdapter):
    @property
    def name(self) -> str:
        return "test-adapter"

    @property
    def system(self) -> ExternalSystem:
        return ExternalSystem(
            system_id="test-system",
            name="Test System",
            system_type=ExternalSystemType.SERVICE,
        )

    def observe(self) -> ExternalSystemObservation:
        return ExternalSystemObservation(
            system=self.system,
            observed_at=datetime.now(timezone.utc),
            state=ExternalObservationState.VERIFIED,
            evidence={
                "status": "available",
            },
            source_name=self.name,
        )


def test_adapter_exposes_stable_name() -> None:
    adapter = TestExternalAdapter()

    assert adapter.name == "test-adapter"


def test_adapter_exposes_external_system() -> None:
    adapter = TestExternalAdapter()

    assert adapter.system.system_id == "test-system"
    assert adapter.system.name == "Test System"
    assert (
        adapter.system.system_type
        is ExternalSystemType.SERVICE
    )


def test_adapter_observes_external_system() -> None:
    adapter = TestExternalAdapter()

    observation = adapter.observe()

    assert isinstance(
        observation,
        ExternalSystemObservation,
    )
    assert observation.system_id == "test-system"
    assert (
        observation.state
        is ExternalObservationState.VERIFIED
    )
    assert observation.evidence["status"] == "available"
    assert observation.source_name == "test-adapter"


def test_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        ExternalIntegrationAdapter()  # type: ignore[abstract]


def test_adapter_does_not_define_authorization_api() -> None:
    adapter = TestExternalAdapter()

    assert not hasattr(adapter, "authorize")
    assert not hasattr(adapter, "is_authorized")
    assert not hasattr(adapter, "grant_authority")
    assert not hasattr(adapter, "approve")


def test_adapter_does_not_define_credential_storage_api() -> None:
    adapter = TestExternalAdapter()

    assert not hasattr(adapter, "credentials")
    assert not hasattr(adapter, "credential")
    assert not hasattr(adapter, "password")
    assert not hasattr(adapter, "token")
    assert not hasattr(adapter, "secret")


def test_adapter_does_not_define_arbitrary_execution_api() -> None:
    adapter = TestExternalAdapter()

    assert not hasattr(adapter, "execute_command")
    assert not hasattr(adapter, "execute_shell")
    assert not hasattr(adapter, "run_script")
    assert not hasattr(adapter, "shell")


def test_adapter_observation_remains_structured() -> None:
    adapter = TestExternalAdapter()

    observation = adapter.observe()

    assert observation.system == adapter.system
    assert observation.source_name == adapter.name


def test_adapter_can_report_external_unavailability() -> None:
    class UnavailableAdapter(ExternalIntegrationAdapter):
        @property
        def name(self) -> str:
            return "unavailable-adapter"

        @property
        def system(self) -> ExternalSystem:
            return ExternalSystem(
                system_id="unavailable-system",
                name="Unavailable System",
                system_type=ExternalSystemType.SERVICE,
            )

        def observe(self) -> ExternalSystemObservation:
            return ExternalSystemObservation(
                system=self.system,
                observed_at=datetime.now(timezone.utc),
                state=ExternalObservationState.UNKNOWN,
                source_name=self.name,
            )

    observation = UnavailableAdapter().observe()

    assert (
        observation.state
        is ExternalObservationState.UNKNOWN
    )
    assert observation.evidence is None


def test_adapter_identity_is_not_mutable() -> None:
    adapter = TestExternalAdapter()

    with pytest.raises(AttributeError):
        adapter.name = "changed"  # type: ignore[misc]


def test_adapter_system_identity_is_not_mutable() -> None:
    adapter = TestExternalAdapter()

    with pytest.raises(AttributeError):
        adapter.system = ExternalSystem(  # type: ignore[misc]
            system_id="other",
            name="Other",
            system_type=ExternalSystemType.SERVICE,
        )