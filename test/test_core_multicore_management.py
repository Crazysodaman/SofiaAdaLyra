"""Actual-state multi-Core management, registration and owner controls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.contracts import EvidenceState, LifecycleState
from sofia.core.multicore.management import (
    CoreControlOperation,
    CoreDefinitionView,
    CoreDisplayState,
    CoreManagementError,
    CoreStopReceipt,
    EXPECTED_CORE_IDENTITIES,
    InMemoryCoreDefinitionSource,
    InstallationEvidence,
    MultiCoreManagement,
    RuntimeObservation,
)
from test._shared_inference_support import MODEL

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def definition(
    number: int, name: str, core_id: UUID | None = None,
    *, generation: int = 1,
) -> CoreDefinitionView:
    return CoreDefinitionView(
        core_id=core_id if core_id is not None else uuid4(),
        full_name=name,
        core_number=number,
        generation=generation,
        lifecycle=LifecycleState.REGISTERED,
        nickname=name,
        identity_concept=f"{name} disposable fixture",
        model=MODEL,
        constitution_sha256="a" * 64,
        definition_revision=1,
    )


class Installations:
    def __init__(self, values=None) -> None:
        self.values = dict(values or {})

    def installation(self, core_id):
        return self.values.get(core_id)


class Runtimes:
    def __init__(self, values=None) -> None:
        self.values = dict(values or {})

    def observation(self, core_id):
        return self.values.get(core_id)


class BrokenDefinitions:
    def definitions(self):
        raise OSError("definition storage unavailable")


class InvalidDefinitions:
    def definitions(self):
        return (object(),)


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls = []

    def authorize(self, *, owner_id, operation, core_id):
        self.calls.append((owner_id, operation, core_id))
        return self.allowed


class StopBackend:
    def __init__(self, *, stopped: bool = True) -> None:
        self.stopped = stopped
        self.calls = []

    def stop(self, *, core_id, generation):
        self.calls.append((core_id, generation))
        return CoreStopReceipt(
            core_id=core_id,
            stopped=self.stopped,
            state="stopped" if self.stopped else "active",
            evidence=EvidenceState.VERIFIED,
            observed_at=NOW,
        )


class Safety:
    def __init__(self, stopped: bool = False) -> None:
        self.stopped = stopped

    def is_operator_stopped(self) -> bool:
        return self.stopped


def management(
    registry, *, installations=None, runtimes=None, stop_backend=None,
    authorization=None, safety=None,
):
    return MultiCoreManagement(
        platform_id="platform:test",
        definitions=registry,
        installation=installations,
        runtime=runtimes,
        stop_backend=stop_backend,
        authorization=authorization,
        safety=safety,
        clock=lambda: NOW,
    )


def test_actual_state_requires_explicit_verified_runtime_evidence() -> None:
    registry = InMemoryCoreDefinitionSource()
    mack = definition(2, "Mack")
    nova = definition(3, "Nova")
    registry.register(mack)
    registry.register(nova)
    installations = Installations({
        mack.core_id: InstallationEvidence(
            mack.core_id, True, EvidenceState.VERIFIED,
            artifact_sha256="b" * 64, version="0.1.0", observed_at=NOW,
        ),
        nova.core_id: InstallationEvidence(
            nova.core_id, False, EvidenceState.VERIFIED,
        ),
    })
    runtimes = Runtimes({
        mack.core_id: RuntimeObservation(
            mack.core_id, "active", mack.generation, NOW, EvidenceState.VERIFIED,
        ),
    })
    snapshot = management(
        registry, installations=installations, runtimes=runtimes,
    ).snapshot()

    rows = {row.full_name: row for row in snapshot.cores}
    assert rows["Mack"].installed is True
    assert rows["Mack"].active is True
    assert rows["Mack"].state is CoreDisplayState.ACTIVE
    assert rows["Nova"].installed is False
    assert rows["Nova"].active is False
    assert rows["Nova"].state is CoreDisplayState.NOT_INSTALLED
    assert snapshot.active_core_count == 1
    assert snapshot.installed_core_count == 1


def test_installed_but_unobserved_is_not_reported_active() -> None:
    registry = InMemoryCoreDefinitionSource()
    mack = definition(2, "Mack")
    registry.register(mack)
    installations = Installations({
        mack.core_id: InstallationEvidence(
            mack.core_id, True, EvidenceState.VERIFIED,
        ),
    })
    snapshot = management(registry, installations=installations).snapshot()
    row = snapshot.cores[0]
    assert row.installed is True
    assert row.active is False
    assert row.state is CoreDisplayState.INSTALLED


def test_unverified_stale_and_wrong_generation_runtime_is_unknown() -> None:
    registry = InMemoryCoreDefinitionSource()
    mack = definition(2, "Mack")
    registry.register(mack)

    reported = Runtimes({
        mack.core_id: RuntimeObservation(
            mack.core_id, "active", mack.generation, NOW,
            EvidenceState.REPORTED,
        ),
    })
    row = management(registry, runtimes=reported).snapshot().cores[0]
    assert row.active is False
    assert row.state is CoreDisplayState.UNKNOWN
    assert "not verified" in row.detail

    stale = Runtimes({
        mack.core_id: RuntimeObservation(
            mack.core_id, "active", mack.generation,
            NOW - timedelta(minutes=10), EvidenceState.VERIFIED,
        ),
    })
    row = management(registry, runtimes=stale).snapshot().cores[0]
    assert row.active is False
    assert row.state is CoreDisplayState.UNKNOWN
    assert "stale" in row.detail

    wrong = Runtimes({
        mack.core_id: RuntimeObservation(
            mack.core_id, "active", mack.generation + 1, NOW,
            EvidenceState.VERIFIED,
        ),
    })
    row = management(registry, runtimes=wrong).snapshot().cores[0]
    assert row.active is False
    assert row.state is CoreDisplayState.UNKNOWN
    assert "generation" in row.detail


def test_core_free_platform_is_a_valid_healthy_snapshot() -> None:
    snapshot = management(InMemoryCoreDefinitionSource()).snapshot()
    assert snapshot.core_free is True
    assert snapshot.cores == ()
    assert snapshot.active_core_count == 0
    assert snapshot.installed_core_count == 0
    assert snapshot.definitions_available is True
    assert all(item.present is False for item in snapshot.expected)


def test_unavailable_or_invalid_definition_source_fails_closed() -> None:
    snapshot = management(BrokenDefinitions()).snapshot()
    assert snapshot.definitions_available is False
    assert snapshot.core_free is None
    assert snapshot.cores == ()
    assert all(item.present is None for item in snapshot.expected)

    with pytest.raises(CoreManagementError):
        management(InvalidDefinitions()).snapshot()


def test_expected_sofia_mack_nova_are_explicit_not_assumed() -> None:
    registry = InMemoryCoreDefinitionSource()
    sofia = definition(1, "SofÃ­a")
    mack = definition(2, "Mack")
    nova = definition(3, "Nova")
    for item in (sofia, mack, nova):
        registry.register(item)
    snapshot = management(registry).snapshot()
    status = {
        item.full_name: item for item in snapshot.expected
    }
    assert [item.full_name for item in EXPECTED_CORE_IDENTITIES] == [
        "Sofía Ada Lyra", "Mack Fuller", "Nova Arden", "Vera", "Core #7",
    ]
    assert status[EXPECTED_CORE_IDENTITIES[0].full_name].present is True
    assert status["Mack Fuller"].present is True
    assert status["Nova Arden"].present is True

    registry.remove(nova.core_id)
    snapshot = management(registry).snapshot()
    status = {item.full_name: item for item in snapshot.expected}
    assert status["Nova Arden"].present is False
    assert status["Nova Arden"].core_id is None
    assert status["Nova Arden"].state is None


def test_owner_controls_require_authorization_and_never_fake_stop() -> None:
    registry = InMemoryCoreDefinitionSource()
    mack = definition(2, "Mack")
    registry.register(mack)

    denied = Authorizer(False)
    service = management(
        registry, authorization=denied, installations=Installations({
            mack.core_id: InstallationEvidence(
                mack.core_id, True, EvidenceState.VERIFIED,
            ),
        }),
    )
    receipt = service.set_participation(
        mack.core_id, owner_id="owner:test", enabled=False,
    )
    assert receipt.allowed is False
    assert receipt.participation_enabled is True
    assert service.snapshot().cores[0].participation_enabled is True

    no_backend = management(
        registry, authorization=Authorizer(True),
    ).request_stop(mack.core_id, owner_id="owner:test")
    assert no_backend.allowed is False
    assert "backend" in (no_backend.reason or "")

    allowed = Authorizer(True)
    backend = StopBackend()
    service = management(
        registry, authorization=allowed, stop_backend=backend,
    )
    changed = service.set_participation(
        mack.core_id, owner_id="owner:test", enabled=False,
    )
    assert changed.allowed is True
    assert service.snapshot().cores[0].participation_enabled is False
    notified = service.set_notifications(
        mack.core_id, owner_id="owner:test", enabled=False,
    )
    assert notified.allowed is True
    assert service.snapshot().cores[0].notifications_enabled is False

    stopped = service.request_stop(mack.core_id, owner_id="owner:test")
    assert stopped.allowed is True
    assert stopped.operation is CoreControlOperation.STOP
    assert backend.calls == [(mack.core_id, mack.generation)]


def test_operator_stop_disables_controls_without_new_state_claims() -> None:
    registry = InMemoryCoreDefinitionSource()
    mack = definition(2, "Mack")
    registry.register(mack)
    backend = StopBackend()
    service = management(
        registry,
        authorization=Authorizer(True),
        stop_backend=backend,
        safety=Safety(True),
        installations=Installations({
            mack.core_id: InstallationEvidence(
                mack.core_id, True, EvidenceState.VERIFIED,
            ),
        }),
    )
    snapshot = service.snapshot()
    assert snapshot.operator_stopped is True
    assert snapshot.core_free is False
    assert snapshot.cores[0].stop_available is False

    receipt = service.set_participation(
        mack.core_id, owner_id="owner:test", enabled=False,
    )
    assert receipt.allowed is False
    assert "STOP" in (receipt.reason or "")
    stopped = service.request_stop(mack.core_id, owner_id="owner:test")
    assert stopped.allowed is False
    assert backend.calls == []
    assert service.snapshot().cores[0].state is CoreDisplayState.INSTALLED


