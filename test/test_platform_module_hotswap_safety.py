"""Real isolated disposable worker failure / hot-unplug regression.

Uses a synthetic signed module *file* and a disposable child process.
Not a signed OS-installed module, installer, live Core or host acceptance.
"""
from datetime import datetime, timezone

import pytest

from sofia.platform.capability import (
    CapabilityRequest, CapabilityResultKind, CapabilitySystem,
)
from sofia.platform.modules import (
    RESEARCH_CAPABILITY_ID, ModuleProcessError, ResearchModuleProcessAdapter,
)
from sofia.platform.run import ProcessState
from test.test_module_lifecycle_v1 import verified_custom
from test.test_platform_module_process_worker import snapshot


def _adapter(tmp_path, digest, generation):
    return ResearchModuleProcessAdapter(
        package_digest=digest, host_identity="host:synthetic-module-test",
        runtime_dir=tmp_path / ("generation-" + str(generation)),
    )


def _invoke(system, *, rationale="synthetic read"):
    cap = system.resolve(RESEARCH_CAPABILITY_ID)
    return system.execute(CapabilityRequest(
        cap, {"snapshot": snapshot(datetime.now(timezone.utc))},
        "private", rationale,
    ))


def test_child_crash_never_reports_ready_or_replays_an_old_generation(tmp_path):
    pkg = verified_custom(
        tmp_path, directory="signed-worker-one",
        capabilities=(RESEARCH_CAPABILITY_ID,),
    )
    adapter = _adapter(tmp_path, pkg.package_digest, 1)
    adapter.start(epoch=1)
    child = adapter._process
    assert child is not None and child.is_alive()
    try:
        child.terminate()
        child.join(5.0)
        assert not child.is_alive()
        assert not adapter.inspect().ready
        assert adapter.observe().state is not ProcessState.RUNNING
        system = CapabilitySystem(authorization_checker=lambda _: True)
        registrations = adapter.capability_registrations()
        system.register_batch(registrations)
        result = _invoke(system, rationale="crashed worker must refuse")
        assert result.kind is CapabilityResultKind.FAILED
        assert result.evidence is None
        with pytest.raises(RuntimeError, match="already started"):
            adapter.start(epoch=2)
        system.unregister_batch(registrations)
        assert system.capability_names() == ()
    finally:
        adapter.stop()
    assert adapter._process is None
    assert adapter._secret is None


def test_signed_worker_hot_unplug_fences_cached_old_handler_and_new_key(tmp_path):
    old_pkg = verified_custom(
        tmp_path, directory="signed-worker-old",
        capabilities=(RESEARCH_CAPABILITY_ID,),
    )
    new_pkg = verified_custom(
        tmp_path, directory="signed-worker-new", version="9.1.0",
        content="MODULE = 'new-version'\n",
        capabilities=(RESEARCH_CAPABILITY_ID,),
    )
    assert old_pkg.package_digest != new_pkg.package_digest
    old = _adapter(tmp_path, old_pkg.package_digest, 1)
    new = _adapter(tmp_path, new_pkg.package_digest, 2)
    allowed = [True]
    system = CapabilitySystem(authorization_checker=lambda _: allowed[0])
    old.start(epoch=1)
    old_regs = old.capability_registrations()
    system.register_batch(old_regs)
    cached_handler = old_regs[0][1]
    stale_capability = old_regs[0][0]
    try:
        assert _invoke(system).kind is CapabilityResultKind.SUCCESS

        # This test authorizer simulates revocation. Production grants are
        # consumed and rechecked by the existing SAFE-owned dispatcher.
        allowed[0] = False
        assert _invoke(system).kind is CapabilityResultKind.UNAUTHORIZED

        # Drain/withdraw the exact old capability batch before the new one.
        system.unregister_batch(old_regs)
        old.stop()
        assert system.capability_names() == ()
        with pytest.raises(ModuleProcessError, match="unavailable"):
            cached_handler(CapabilityRequest(
                stale_capability,
                {"snapshot": snapshot(datetime.now(timezone.utc))},
                "private", "cached handler must fail",
            ))
        new.start(epoch=2)
        new_regs = new.capability_registrations()
        system.register_batch(new_regs)

        # Revocation still holds across a provider swap until new authority.
        assert _invoke(system).kind is CapabilityResultKind.UNAUTHORIZED
        allowed[0] = True
        assert _invoke(system).kind is CapabilityResultKind.SUCCESS
        assert new.inspect().package_digest == new_pkg.package_digest
        assert not old.inspect().ready
    finally:
        system.unregister_batch(new_regs) if "new_regs" in locals() and (
            RESEARCH_CAPABILITY_ID in system.capability_names()
        ) else None
        old.stop()
        new.stop()
    assert system.capability_names() == ()
    assert new._process is None and new._secret is None


def test_actual_safe_stop_allows_owner_approved_pause_but_denies_resume(
    canonical_state_path, tmp_path,
):
    """Real canonical SAFE approval + STOP, not the test-only callback above."""
    from datetime import timedelta

    from sofia.platform.capability import Capability
    from sofia.platform.modules import ModuleLifecycle, OperationProfileKind
    from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
    from sofia.platform.safe.operator_stop import OperatorStopStore
    from test.test_module_lifecycle_v1 import compatibility
    from test.test_platform_module_command_service import authorize, service

    now = datetime.now(timezone.utc).replace(microsecond=0)
    pkg = verified_custom(
        tmp_path, directory="signed-stop-module",
        capabilities=("research.search",),
    )
    command = service(canonical_state_path, tmp_path)
    found = command.discover(pkg, now=now)
    approve_id, _ = authorize(
        canonical_state_path, operation="approve", record=found,
        target=ModuleLifecycle.APPROVED, now=now,
    )
    approved = command.approve(
        found.module_id, expected_revision=found.revision,
        approval_id=approve_id, now=now,
    )
    stage_id, _ = authorize(
        canonical_state_path, operation="stage", record=approved,
        target=ModuleLifecycle.STAGED, now=now,
    )
    staged = command.stage(
        pkg, expected_revision=approved.revision,
        approval_id=stage_id, now=now,
    )
    activate_id, _ = authorize(
        canonical_state_path, operation="activate", record=staged,
        target=ModuleLifecycle.ACTIVE, profile=OperationProfileKind.OBSERVE,
        now=now,
    )
    active = command.activate(
        pkg, expected_revision=staged.revision,
        approval_id=activate_id, now=now,
        profile=OperationProfileKind.OBSERVE,
        compatibility=compatibility(pkg),
        registrations=((Capability("research.search", "search"), lambda _: None),),
    )
    assert active.lifecycle is ModuleLifecycle.ACTIVE
    assert command.manager.capability_system.capability_names() == ("research.search",)

    OperatorStopStore(canonical_state_path).set(
        active=True, updated_by="Sparks", reason="synthetic worker STOP test",
        at=now + timedelta(seconds=1),
    )
    pause_id, _ = authorize(
        canonical_state_path, operation="pause", record=active,
        target=ModuleLifecycle.PAUSED, now=now + timedelta(seconds=2),
    )
    paused = command.pause(
        active.module_id, expected_revision=active.revision,
        approval_id=pause_id, now=now + timedelta(seconds=2),
    )
    assert paused.lifecycle is ModuleLifecycle.PAUSED
    assert command.manager.capability_system.capability_names() == ()

    resume_time = now + timedelta(seconds=3)
    resume_id, resume_parameters = authorize(
        canonical_state_path, operation="resume", record=paused,
        target=ModuleLifecycle.ACTIVE, profile=OperationProfileKind.OBSERVE,
        now=resume_time,
    )
    with pytest.raises(PermissionError, match="not authorized"):
        command.resume(
            pkg, expected_revision=paused.revision,
            profile=OperationProfileKind.OBSERVE,
            compatibility=compatibility(pkg),
            registrations=((Capability("research.search", "search"), lambda _: None),),
            approval_id=resume_id, now=resume_time,
        )
    assert command.describe(paused.module_id) == paused
    assert ExecutionApprovalVerifier(canonical_state_path).matches_unconsumed(
        approval_id=resume_id, capability="module.resume",
        parameters=resume_parameters, now=resume_time,
    )
