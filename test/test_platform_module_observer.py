from datetime import datetime, timedelta, timezone
import sqlite3

from sofia.core.modreg.platform import ModuleObservationKind
from sofia.platform.capability import CapabilitySystem
from sofia.platform.modules import (
    CanonicalPlatformModuleObserver,
    ModuleLifecycleManager,
)
from test.test_module_lifecycle_v1 import verified_custom


def _insert(path, *, module_id, lifecycle, updated_at, version="1.0.0"):
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO platform_module_lifecycle VALUES(?,?,?,?,1,?,?,?,?)",
            (
                module_id, version, "a" * 64, lifecycle, "observe", None,
                "test lifecycle evidence", updated_at.isoformat(),
            ),
        )


def test_canonical_observer_projects_installed_and_fresh_active_state(
    canonical_state_path, tmp_path,
):
    ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    now = datetime.now(timezone.utc)
    _insert(
        canonical_state_path, module_id="sofia.module.trains",
        lifecycle="active", updated_at=now,
    )

    observer = CanonicalPlatformModuleObserver(canonical_state_path)

    [described] = observer.described()
    [health] = observer.health()
    assert described.module_id == "sofia.module.trains"
    assert described.capabilities == ()
    assert health.lifecycle == "ACTIVE"
    assert health.health is ModuleObservationKind.HEALTHY
    assert observer.outcomes() == ()


def test_stale_active_row_is_not_live_health(canonical_state_path, tmp_path):
    ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    _insert(
        canonical_state_path, module_id="sofia.module.stale",
        lifecycle="active",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )

    [health] = CanonicalPlatformModuleObserver(canonical_state_path).health()

    assert health.lifecycle == "ACTIVE"
    assert health.health is ModuleObservationKind.UNKNOWN_STATE
    assert health.reason_codes == ("active-observation-stale",)


def test_missing_lifecycle_table_is_honest_empty_projection(
    canonical_state_path,
):
    observer = CanonicalPlatformModuleObserver(canonical_state_path)
    assert observer.described() == ()
    assert observer.health() == ()


def test_observer_projects_signed_declared_capabilities_without_importing_code(
    canonical_state_path, tmp_path,
):
    package = verified_custom(
        tmp_path, directory="source", module_id="org.sofia.observer",
        capabilities=("tool.catalog", "module.example.mutate"),
    )
    manager = ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: True,
    )
    found = manager.discover(package, now=datetime.now(timezone.utc))
    approved = manager.approve(
        found.module_id, expected_revision=found.revision,
        operation_ref="approval:approve", actor="Sparks",
        now=datetime.now(timezone.utc),
    )
    manager.stage(
        package, expected_revision=approved.revision,
        operation_ref="approval:stage", actor="Sparks",
        now=datetime.now(timezone.utc),
    )

    [described] = CanonicalPlatformModuleObserver(
        canonical_state_path
    ).described()
    assert described.capabilities == (
        "module.example.mutate", "tool.catalog",
    )
    assert described.requires_permission == frozenset({
        "module.example.mutate",
    })
    assert described.simulated_only == frozenset()
