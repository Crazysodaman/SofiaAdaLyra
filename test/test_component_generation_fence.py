from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.platform.run import ComponentGenerationStore, GenerationState, LocalRunLeaseStore
from sofia.sdk import ComponentKind


NOW = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)


def setup(canonical_state_path):
    leases = LocalRunLeaseStore(canonical_state_path)
    lease = leases.acquire(
        owner_id="platform:supervisor", now=NOW, ttl_seconds=300,
    ).lease
    assert lease is not None
    return leases, lease, ComponentGenerationStore(
        state_path=canonical_state_path, lease_store=leases,
    )


def stage(store, lease, digest=b"core"):
    return store.stage(
        component_id="core.sofia", kind=ComponentKind.CORE,
        release_digest=sha256(digest).hexdigest(),
        platform_instance_id="platform:test", core_identity_id="core:sofia",
        lease=lease, now=NOW, reason="reviewed release",
    )


def test_exactly_one_active_generation_and_explicit_drain_fence(canonical_state_path):
    _, lease, store = setup(canonical_state_path)
    first = stage(store, lease)
    second = stage(store, lease, b"core-v2")
    store.activate(first, lease=lease, now=NOW, reason="initial activation")
    assert store.is_active(first) is True
    assert store.active_for_component("core.sofia") == first
    with pytest.raises(RuntimeError, match="already active"):
        store.activate(second, lease=lease, now=NOW, reason="unsafe collision")
    store.begin_drain(
        first, lease=lease, now=NOW + timedelta(seconds=1), reason="update drain",
    )
    assert store.is_active(first) is False
    store.fence(
        first, lease=lease, now=NOW + timedelta(seconds=2), reason="worker stopped",
    )
    assert store.active_for_component("core.sofia") is None
    store.activate(
        second, lease=lease, now=NOW + timedelta(seconds=3), reason="replacement",
    )
    assert store.state(first) is GenerationState.RETIRED
    assert store.is_active(second) is True
    assert store.active_for_component("core.sofia") == second


def test_restart_preserves_fence_and_stale_identity_cannot_reactivate(canonical_state_path):
    leases, lease, store = setup(canonical_state_path)
    endpoint = stage(store, lease)
    store.activate(endpoint, lease=lease, now=NOW, reason="activate")
    reopened = ComponentGenerationStore(
        state_path=canonical_state_path, lease_store=leases,
    )
    assert reopened.is_active(endpoint) is True
    reopened.begin_drain(
        endpoint, lease=lease, now=NOW + timedelta(seconds=1), reason="drain",
    )
    reopened.fence(
        endpoint, lease=lease, now=NOW + timedelta(seconds=2), reason="fence",
        quarantine=True,
    )
    assert reopened.is_active(endpoint) is False
    assert reopened.state(endpoint) is GenerationState.QUARANTINED
    with pytest.raises(RuntimeError, match="changed"):
        reopened.activate(
            endpoint, lease=lease, now=NOW + timedelta(seconds=3), reason="replay",
        )


def test_expired_or_different_run_lease_cannot_change_generations(canonical_state_path):
    leases, lease, store = setup(canonical_state_path)
    endpoint = stage(store, lease)
    replacement = leases.acquire(
        owner_id="platform:new", now=NOW + timedelta(minutes=6), ttl_seconds=300,
    ).lease
    assert replacement is not None
    with pytest.raises(PermissionError, match="lease"):
        store.activate(
            endpoint, lease=lease, now=NOW + timedelta(minutes=6), reason="stale",
        )
    store.activate(
        endpoint, lease=replacement, now=NOW + timedelta(minutes=6),
        reason="reconciled owner",
    )
    assert store.is_active(endpoint)
