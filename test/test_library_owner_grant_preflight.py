"""Single-owner headless Library grant planning on real disposable RUN state.

No SAFE owner grant is created in any test. Existing attended permission CLI
still must consume a separate signed one-use owner approval to grant access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os

import pytest

from sofia.platform.ops.library_owner_cli import main
from sofia.platform.ops.library_owner_grant_preflight import (
    OwnerLibraryPreflightDenied, preview_personal_hub_grant,
    preview_personal_local_read_grant,
)
from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore
from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from test.test_platform_service_session import provision


def _owner(tmp_path):
    identity, current, state = provision(tmp_path)
    owner = OwnerLibraryTrustStore(
        state, platform_id=current.identity.canonical_uuid,
    )
    return identity, current, state, owner


def test_hub_and_read_preview_uses_actual_run_without_creating_grants(tmp_path):
    identity, current, state, owner = _owner(tmp_path)
    permissions = PermissionStore(state)
    with pytest.raises(OwnerLibraryPreflightDenied, match="RUN"):
        preview_personal_hub_grant(
            store=owner, bind_host="127.0.0.1", bind_port=47321,
        )
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        status = service.status()
        hub = preview_personal_hub_grant(
            store=owner, bind_host="127.0.0.1", bind_port=47321,
        )
        read = preview_personal_local_read_grant(
            store=owner,
            native_peer=lambda: "unix:uid:1234:gid:5678",
        )
        assert hub["run_generation"] == status["generation"]
        assert hub["scope"]["source_generation"] == status["generation"]
        assert hub["scope"]["platform_id"] == status["platform_id"]
        assert hub["scope"]["bind_host"] == "127.0.0.1"
        assert hub["capability"] == "platform.library.hub.serve"
        assert read["capability"] == "platform.library.read"
        assert read["scope"]["peer"] == "unix:uid:1234:gid:5678"
        for preview in (hub, read):
            assert preview["owner_mode"] == "SINGLE_OWNER_PRIVATE"
            assert preview["owner_proof_consumed"] is False
            assert preview["grant_created"] is False
            assert preview["listener_started"] is False
            assert preview["core_activated"] is False
            assert json.loads(preview["scope_json"]) == preview["scope"]
    assert not any(
        grant.capability in {"platform.library.hub.serve", "platform.library.read"}
        for grant in permissions.grants(active_only=False)
    )


def test_hub_preview_denies_wildcard_and_nonprivate_bind(tmp_path):
    identity, current, state, owner = _owner(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ):
        for address in ("0.0.0.0", "8.8.8.8", "example.org"):
            with pytest.raises((PermissionError, ValueError)):
                preview_personal_hub_grant(
                    store=owner, bind_host=address, bind_port=47321,
                )
        for port in (0, 65536, True):
            with pytest.raises((PermissionError, ValueError)):
                preview_personal_hub_grant(
                    store=owner, bind_host="127.0.0.1", bind_port=port,
                )


def test_owner_stop_and_lost_lease_make_preview_unavailable(tmp_path):
    identity, current, state, owner = _owner(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ):
        owner.stop.set(
            active=True, updated_by="test-only-owner",
            reason="owner test STOP", at=datetime.now(timezone.utc),
        )
        with pytest.raises(OwnerLibraryPreflightDenied, match="STOP"):
            preview_personal_local_read_grant(
                store=owner,
                native_peer=lambda: "unix:uid:1234:gid:5678",
            )
    with pytest.raises(OwnerLibraryPreflightDenied, match="RUN|STOP"):
        preview_personal_hub_grant(
            store=owner, bind_host="127.0.0.1", bind_port=47321,
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX real current UID/GID")
def test_existing_owner_cli_preflight_never_grants_or_opens_listener(
    tmp_path, capsys,
):
    identity, current, state, owner = _owner(tmp_path)
    platform_id = current.identity.canonical_uuid
    with PlatformServiceSession(
        identity.home, state, platform_id, current.public_key_sha256,
    ) as service:
        assert main([
            "--state", str(state), "--platform-id", platform_id,
            "prepare-local-read",
        ]) == 0
        native = json.loads(capsys.readouterr().out)
        assert native["scope"]["peer"] == (
            f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        )
        assert main([
            "--state", str(state), "--platform-id", platform_id,
            "prepare-private-hub", "--bind-host", "127.0.0.1",
            "--bind-port", "47321",
        ]) == 0
        hub = json.loads(capsys.readouterr().out)
        assert hub["scope"]["source_generation"] == service.status()["generation"]
        assert hub["grant_created"] is False
        assert hub["authorization_required"] == "EXISTING_OWNER_SAFE_ONE_USE"
        assert not service._hosted_library_hubs



def test_readonly_preflight_does_not_initialize_or_write_lease_schema(
    tmp_path, monkeypatch,
):
    """A status preview must not call the write-capable RUN store constructor."""
    from sofia.platform.run.lease import LocalRunLeaseStore
    from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
    identity, current, state, owner = _owner(tmp_path)
    # Existing installation bootstrap may have schema, but previewing must
    # not initialize RUN state, migrate tables or acquire a lease.
    with CanonicalSQLiteGuard(state).connect(read_only=True) as db:
        before = tuple(db.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
    def reject_constructor(*_args, **_kwargs):
        raise AssertionError("read-only preflight attempted RUN writer construction")
    monkeypatch.setattr(LocalRunLeaseStore, "__init__", reject_constructor)
    with pytest.raises(OwnerLibraryPreflightDenied, match="RUN"):
        preview_personal_hub_grant(
            store=owner, bind_host="127.0.0.1", bind_port=47321,
        )
    with CanonicalSQLiteGuard(state).connect(read_only=True) as db:
        after = tuple(db.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
    assert before == after


def test_pinned_readonly_lease_observer_matches_real_service_run(tmp_path):
    from sofia.platform.run.lease import LocalRunLeaseStore
    identity, current, state, owner = _owner(tmp_path)
    at = datetime.now(timezone.utc)
    assert LocalRunLeaseStore.peek_existing(
        state, lease_key="platform-service", now=at,
    ) is None
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        observed = service.status()
        pin = LocalRunLeaseStore.peek_existing(
            state, lease_key="platform-service",
            now=datetime.now(timezone.utc),
        )
        assert pin is not None
        assert pin.epoch == observed["generation"]
        assert pin.lease_key == "platform-service"
        assert pin.owner_id
    assert LocalRunLeaseStore.peek_existing(
        state, lease_key="platform-service", now=datetime.now(timezone.utc),
    ) is None


def test_readonly_lease_observer_refuses_future_clock_and_invalid_inputs(tmp_path):
    from datetime import timedelta
    from sofia.platform.run.lease import LocalRunLeaseStore
    identity, current, state, owner = _owner(tmp_path)
    with pytest.raises(ValueError, match="timezone-aware"):
        LocalRunLeaseStore.peek_existing(
            state, lease_key="platform-service", now=datetime.utcnow(),
        )
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        assert LocalRunLeaseStore.peek_existing(
            state, lease_key="platform-service",
            now=datetime.now(timezone.utc) + timedelta(hours=1),
        ) is None

def test_owner_cli_previews_separate_short_lived_sources_read_scope(
    tmp_path, capsys,
):
    identity, current, state, owner = _owner(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ):
        assert main([
            "--state", str(state), "--platform-id", current.identity.canonical_uuid,
            "prepare-local-read", "--operation", "library.sources.snapshot.v1",
        ]) == 0
        preview = json.loads(capsys.readouterr().out)
        assert preview["scope"]["operation"] == "library.sources.snapshot.v1"
        assert preview["capability"] == "platform.library.read"
        assert preview["grant_created"] is False
        assert preview["authorization_required"] == "EXISTING_OWNER_SAFE_ONE_USE"
        with pytest.raises(OwnerLibraryPreflightDenied, match="exact catalog"):
            preview_personal_local_read_grant(
                store=owner, operation="library.install.execute.v1",
            )
