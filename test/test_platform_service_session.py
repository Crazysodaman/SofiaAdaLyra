"""Core-free service composition uses existing identity and RUN owners."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.run.core_autostart import (
    CoreAutostartPolicyStore, CoreStartupReconciler,
)
from sofia.platform.state.installation_identity import InstallationIdentityStore
from sofia.platform.state.local_store import PlatformLocalStore
from sofia.platform.run.platform_service import PlatformServiceSession


def provision(tmp_path):
    identity = InstallationIdentityStore(tmp_path/'identity')
    current = identity.initialize()
    state = tmp_path/'platform.db'
    PlatformLocalStore(state, roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        host_identity=current.identity.canonical_uuid)
    return identity, current, state


def test_session_reuses_identity_and_excludes_duplicate_until_closed(tmp_path):
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256) as first:
        assert first.status()['core_started'] is False
        assert first.status()['platform_id'] == current.identity.canonical_uuid
        epoch = first.lease.epoch
        with pytest.raises(RuntimeError):
            PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256)
    with PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256) as second:
        assert second.lease.epoch > epoch
    assert identity.load() == current
    assert not list(tmp_path.rglob('sofia.db'))


def test_session_refuses_missing_state_and_wrong_identity(tmp_path):
    identity, current, state = provision(tmp_path)
    with pytest.raises(PermissionError):
        PlatformServiceSession(identity.home, state, str(uuid4()), current.public_key_sha256)
    state.unlink()
    with pytest.raises(PermissionError):
        PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256)
    assert not state.exists()


def test_session_refuses_lost_identity_before_health(tmp_path):
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256) as session:
        identity.metadata_path.unlink()
        with pytest.raises(RuntimeError):
            session.status()


def test_lifetime_lock_survives_lease_loss_and_different_temp_namespace(tmp_path, monkeypatch):
    import tempfile
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256) as first:
        first.leases.release(first.lease, now=datetime.now(timezone.utc))
        other = tmp_path/'other-temp'
        other.mkdir()
        monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(other))
        with pytest.raises(RuntimeError):
            PlatformServiceSession(identity.home, state, current.identity.canonical_uuid, current.public_key_sha256)


def reconciler(state, start_core, *, is_stopped=lambda: False):
    store = CoreAutostartPolicyStore(state, verify_approval=lambda **_: True)
    return store, CoreStartupReconciler(
        store=store, start_core=start_core, is_stopped=is_stopped,
    )


def test_service_zero_core_autostart_is_healthy_without_starting_core(tmp_path):
    identity, current, state = provision(tmp_path)
    started = []
    _store, startup = reconciler(state, lambda *args: started.append(args))
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256, core_autostart=startup,
    ) as session:
        status = session.startup_status()
        assert set(status) == {
            'core_count', 'active_core_count', 'startup_state',
            'autostart_enabled_count', 'autostart_reconciled_at',
            'management_listening',
        }
        assert status['startup_state'] == 'ZERO_CORE_HEALTHY'
        assert status['core_count'] == 0
        assert status['active_core_count'] == 0
        assert status['autostart_enabled_count'] == 0
        assert status['management_listening'] is True
        assert session.status()['management_listening'] is True
    assert started == []


def test_service_approved_core_autostarts_and_failure_stays_platform_healthy(tmp_path):
    identity, current, state = provision(tmp_path)
    calls = []

    def start_core(core_id, generation, approval_ref):
        calls.append((core_id, generation, approval_ref))
        return 'STARTED'

    store, startup = reconciler(state, start_core)
    core_id = str(uuid4())
    store.set_enabled(
        core_id=core_id, enabled=True, revision=1,
        approval_ref='approval:service', now=datetime.now(timezone.utc),
    )
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256, core_autostart=startup,
    ) as session:
        status = session.startup_status()
        assert calls and calls[0][0] == core_id
        assert status['startup_state'] == 'HEALTHY'
        assert status['core_count'] == 1
        assert status['active_core_count'] == 1
        assert status['autostart_enabled_count'] == 1
        assert session.status()['management_listening'] is True


def test_service_core_start_failure_degrades_startup_not_platform(tmp_path):
    identity, current, state = provision(tmp_path)

    def start_core(_core_id, _generation, _approval_ref):
        raise RuntimeError('process backend unavailable')

    store, startup = reconciler(state, start_core)
    core_id = str(uuid4())
    store.set_enabled(
        core_id=core_id, enabled=True, revision=1,
        approval_ref='approval:service-failure',
        now=datetime.now(timezone.utc),
    )
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256, core_autostart=startup,
    ) as session:
        status = session.startup_status()
        assert status['startup_state'] in {'DEGRADED', 'UNKNOWN'}
        assert status['core_count'] == 1
        assert status['active_core_count'] == 0
        assert session.status()['management_listening'] is True
        assert session.status()['core_started'] is False
