from datetime import datetime, timezone
from hashlib import sha256

import pytest

from sofia.platform.run import (
    ComponentKind,
    ComponentRuntimeSupervisor,
    ComponentSpec,
    ComponentUpdateCandidate,
    ComponentGenerationStore,
    LocalRunLeaseStore,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
    UpdateChangeKind,
)
from sofia.sdk import ComponentKind as SDKComponentKind


NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


class Backend(ManagedRuntimeBackend):
    def observe(self):
        return RuntimeObservation(ProcessState.RUNNING, ready=True)

    def start(self, *, epoch):
        raise AssertionError("impact planning must not start a component")

    def stop(self):
        raise AssertionError("impact planning must not stop a component")


def candidate(kind, component_id=None, **changes):
    values = dict(
        change_kind=kind,
        component_id=component_id,
        source_digest=sha256(b"old").hexdigest(),
        target_digest=sha256(b"new").hexdigest(),
        compatibility_verified=True,
    )
    values.update(changes)
    return ComponentUpdateCandidate(**values)


def supervisor(path, now):
    leases = LocalRunLeaseStore(path)
    result = ComponentRuntimeSupervisor(state_path=path, lease_store=leases)
    for spec in (
        ComponentSpec("platform", ComponentKind.PLATFORM),
        ComponentSpec("core", ComponentKind.CORE, dependencies=("platform",)),
        ComponentSpec("inference", ComponentKind.INFERENCE, dependencies=("platform",)),
        ComponentSpec("voice", ComponentKind.OPTIONAL_MODULE, dependencies=("core",)),
        ComponentSpec("avatar", ComponentKind.OPTIONAL_MODULE, dependencies=("voice",)),
        ComponentSpec("research", ComponentKind.OPTIONAL_MODULE, dependencies=("core",)),
    ):
        result.register(spec, Backend(), now=now)
    lease = leases.acquire(
        owner_id="platform-impact-planner", now=now, ttl_seconds=300,
    ).lease
    assert lease is not None
    generations = ComponentGenerationStore(state_path=path, lease_store=leases)
    sdk_kinds = {
        "platform": SDKComponentKind.PLATFORM,
        "core": SDKComponentKind.CORE,
        "inference": SDKComponentKind.INFERENCE,
        "voice": SDKComponentKind.MODULE,
        "avatar": SDKComponentKind.MODULE,
        "research": SDKComponentKind.MODULE,
    }
    for component_id, kind in sdk_kinds.items():
        endpoint = generations.stage(
            component_id=component_id,
            kind=kind,
            release_digest=sha256(b"old").hexdigest(),
            platform_instance_id="platform:test",
            core_identity_id=("core:test" if kind is SDKComponentKind.CORE else None),
            lease=lease,
            now=now,
            reason="impact test active release",
        )
        generations.activate(
            endpoint, lease=lease, now=now, reason="impact test activation",
        )
    return result


def test_module_update_pauses_only_transitive_dependents(canonical_state_path):
    runtime = supervisor(canonical_state_path, NOW)
    plan = runtime.plan_update(candidate(UpdateChangeKind.MODULE_ONLY, "voice"))
    assert plan.drain_components == ("voice",)
    assert plan.pause_dependents == ("avatar",)
    assert plan.unaffected_components == ("core", "inference", "platform", "research")
    assert plan.impact_resolved
    assert not plan.platform_restart_required


def test_core_and_inference_updates_preserve_unrelated_components(
    canonical_state_path,
):
    runtime = supervisor(canonical_state_path, NOW)
    core = runtime.plan_update(candidate(UpdateChangeKind.CORE_ONLY, "core"))
    assert core.drain_components == ("core",)
    assert core.pause_dependents == ("avatar", "research", "voice")
    assert core.unaffected_components == ("inference", "platform")
    provider = runtime.plan_update(
        candidate(UpdateChangeKind.INFERENCE_ONLY, "inference")
    )
    assert provider.drain_components == ("inference",)
    assert provider.pause_dependents == ()
    assert provider.unaffected_components == (
        "avatar", "core", "platform", "research", "voice",
    )


@pytest.mark.parametrize("compatibility,reason", [
    (None, "compatibility_unknown"),
    (False, "compatibility_failed"),
])
def test_unknown_or_failed_compatibility_blocks_activation(
    canonical_state_path, compatibility, reason,
):
    runtime = supervisor(canonical_state_path, NOW)
    plan = runtime.plan_update(candidate(
        UpdateChangeKind.MODULE_ONLY, "voice",
        compatibility_verified=compatibility,
    ))
    assert plan.blocked
    assert reason in plan.blocked_reasons
    assert not plan.impact_resolved


def test_kind_mismatch_and_unknown_target_fail_closed(canonical_state_path):
    runtime = supervisor(canonical_state_path, NOW)
    mismatch = runtime.plan_update(
        candidate(UpdateChangeKind.CORE_ONLY, "voice")
    )
    assert mismatch.blocked_reasons == ("target_component_kind_mismatch",)
    missing = runtime.plan_update(
        candidate(UpdateChangeKind.MODULE_ONLY, "missing")
    )
    assert missing.blocked_reasons == ("target_component_unknown",)


def test_stale_or_missing_active_release_evidence_fails_closed(
    canonical_state_path,
):
    runtime = supervisor(canonical_state_path, NOW)
    stale = runtime.plan_update(ComponentUpdateCandidate(
        UpdateChangeKind.MODULE_ONLY,
        sha256(b"stale").hexdigest(),
        sha256(b"new").hexdigest(),
        "voice",
        True,
    ))
    assert stale.blocked_reasons == ("source_release_mismatch",)

    runtime.register(
        ComponentSpec("untracked", ComponentKind.OPTIONAL_MODULE), Backend(), now=NOW,
    )
    missing = runtime.plan_update(
        candidate(UpdateChangeKind.MODULE_ONLY, "untracked")
    )
    assert missing.blocked_reasons == ("source_release_unknown",)


def test_shared_abi_broadens_exact_consumer_scope(canonical_state_path):
    runtime = supervisor(canonical_state_path, NOW)
    plan = runtime.plan_update(candidate(
        UpdateChangeKind.SHARED_ABI,
        abi_consumers=("core", "inference"),
    ))
    assert plan.drain_components == ("core", "inference")
    assert plan.pause_dependents == ("avatar", "research", "voice")
    assert plan.unaffected_components == ("platform",)
    assert not plan.platform_restart_required
    assert plan.impact_resolved


def test_platform_abi_and_state_schema_require_platform_restart(
    canonical_state_path,
):
    runtime = supervisor(canonical_state_path, NOW)
    abi = runtime.plan_update(candidate(
        UpdateChangeKind.SHARED_ABI, abi_consumers=("platform",),
    ))
    assert abi.platform_restart_required
    assert set(abi.drain_components) == {"platform"}
    assert set(abi.pause_dependents) == {
        "avatar", "core", "inference", "research", "voice",
    }
    schema = runtime.plan_update(candidate(UpdateChangeKind.STATE_SCHEMA))
    assert schema.platform_restart_required
    assert set(schema.drain_components) == {
        "avatar", "core", "inference", "platform", "research", "voice",
    }


def test_data_only_requires_explicit_atomic_reload_support(
    canonical_state_path,
):
    runtime = supervisor(canonical_state_path, NOW)
    blocked = runtime.plan_update(candidate(UpdateChangeKind.DATA_ONLY))
    assert blocked.blocked_reasons == ("atomic_reload_not_supported",)
    live = runtime.plan_update(candidate(
        UpdateChangeKind.DATA_ONLY, atomic_reload_supported=True,
    ))
    assert not live.blocked
    assert live.drain_components == ()
    assert live.pause_dependents == ()
    assert live.impact_resolved


def test_same_release_identity_is_not_an_update():
    digest = sha256(b"same").hexdigest()
    with pytest.raises(ValueError, match="must differ"):
        ComponentUpdateCandidate(
            UpdateChangeKind.CORE_ONLY, digest, digest, "core", True,
        )
