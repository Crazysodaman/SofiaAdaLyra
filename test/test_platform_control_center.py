from datetime import datetime, timezone
import sqlite3

from sofia.platform.capability import CapabilitySystem
from sofia.platform.modules import (
    ModuleLifecycleManager,
    platform_control_center_text,
    platform_module_manager_text,
)
from test.test_platform_module_observer import _insert
from test.test_platform_module_operations import finish, prepared
from test.test_module_lifecycle_v1 import verified_custom


def test_control_center_labels_unverified_lifecycle_and_absent_runtime_state(
    canonical_state_path, tmp_path,
):
    ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    _insert(
        canonical_state_path,
        module_id="org.sofia.unverified",
        lifecycle="active",
        updated_at=datetime.now(timezone.utc),
    )

    rendered = platform_control_center_text(canonical_state_path)

    assert "org.sofia.unverified" in rendered
    assert "health=unknown_state" in rendered
    assert "active-observation-missing-or-stale" in rendered
    assert "UNKNOWN — canonical RUN table is absent" in rendered
    assert "UNKNOWN — canonical module-operation journal is absent" in rendered
    assert "UNKNOWN — no live application factory registry" in rendered
    with sqlite3.connect(canonical_state_path) as db:
        names = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "autonomous_work_job" not in names
    assert "platform_module_operation_request" not in names


def test_control_center_uses_real_run_observation_without_disclosing_authority(
    canonical_state_path, tmp_path,
):
    lifecycle, coordinator, manager, store, _adapter, request, _ = prepared(
        canonical_state_path, tmp_path,
    )
    try:
        job = coordinator.submit(request, now=datetime.now(timezone.utc))
        settled = finish(manager, store, job.job_id)
        rendered = platform_control_center_text(
            canonical_state_path, factories=coordinator.factories,
        )
    finally:
        manager.close(wait=True)

    assert settled.status.value == "completed"
    assert "health=healthy" in rendered
    assert (
        f"{job.job_id} kind=platform.module.operation status=completed"
        in rendered
    )
    assert f"{request.request_id} module={request.module_id}" in rendered
    assert "latest=externally_verified_success" in rendered
    assert "evidence_recorded=True" in rendered
    assert "factory:research" in rendered
    # The operator projection exposes status metadata, not reusable authority
    # or the RUN payload that carries it.
    assert request.approval_id not in rendered
    assert request.principal_attestation_ref not in rendered
    assert request.requested_effect not in rendered
    assert request.principal.principal_id not in rendered


def test_module_manager_keeps_lifecycle_health_readiness_and_authority_separate(
    canonical_state_path, tmp_path,
):
    ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    _insert(
        canonical_state_path,
        module_id="org.sofia.manager",
        lifecycle="active",
        updated_at=datetime.now(timezone.utc),
        package_digest="b" * 64,
    )
    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "INSERT INTO platform_module_dependency VALUES(?,?,?,?)",
            ("org.sofia.manager", "org.sofia.base", "1.2.0", "2.0.0"),
        )
        db.execute(
            "INSERT INTO platform_module_capability VALUES(?,?,?)",
            ("org.sofia.manager", "system.service.restart", "schema:restart:v1"),
        )
        db.execute(
            "INSERT INTO platform_module_policy VALUES(?,?,?,?)",
            ("org.sofia.manager", "b" * 64, "local", "subprocess-restricted"),
        )

    rendered = platform_module_manager_text(canonical_state_path)

    assert "org.sofia.manager version=1.0.0 installed=true" in rendered
    assert "lifecycle=ACTIVE" in rendered
    assert "health=UNKNOWN_STATE" in rendered
    assert "readiness=BETA" in rendered
    assert "org.sofia.base (>=1.2.0,<2.0.0)" in rendered
    assert "capabilities=system.service.restart" in rendered
    assert "protected=system.service.restart" in rendered
    assert "effective_authority=UNKNOWN" in rendered
    assert "policy_identity=verified" in rendered
    assert "signed_resources=UNKNOWN" in rendered
    assert "module_settings=UNSUPPORTED" in rendered


def test_module_manager_projects_exact_signed_resource_and_maintenance_policy(
    canonical_state_path, tmp_path,
):
    package = verified_custom(
        tmp_path, directory="signed-policy",
        module_id="org.sofia.manager.policy",
    )
    lifecycle = ModuleLifecycleManager(
        state_path=canonical_state_path,
        store_root=tmp_path / "module-store",
        capability_system=CapabilitySystem(lambda request: False),
        authorizer=lambda request: False,
    )
    lifecycle.discover(package, now=datetime.now(timezone.utc))

    rendered = platform_module_manager_text(canonical_state_path)

    assert "org.sofia.manager.policy version=9.0.0 installed=false" in rendered
    assert "signed_resources=ram_mib=128" in rendered
    assert "profiles=OBSERVE(ceiling=1)" in rendered
    assert "maintenance=support=supported;retries=2;quarantine_threshold=3" in rendered
    assert "probes=process.health" in rendered
    assert "module_settings=UNSUPPORTED" in rendered

    with sqlite3.connect(canonical_state_path) as db:
        db.execute(
            "UPDATE platform_module_manifest_projection SET manifest_json='{}' "
            "WHERE module_id=?", (package.manifest.module_id,),
        )
    tampered = platform_module_manager_text(canonical_state_path)
    assert "signed_resources=UNKNOWN" in tampered
    assert "maintenance=UNKNOWN" in tampered
