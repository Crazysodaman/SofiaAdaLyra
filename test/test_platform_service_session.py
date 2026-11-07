"""Core-free service composition uses existing identity and RUN owners."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
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
