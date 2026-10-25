from datetime import datetime, timezone
import sqlite3

from sofia.platform.capability import CapabilitySystem
from sofia.platform.modules import (
    ModuleLifecycleManager,
    platform_control_center_text,
)
from test.test_platform_module_observer import _insert
from test.test_platform_module_operations import finish, prepared


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
