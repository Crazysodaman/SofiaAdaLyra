"""Real service lease and local native management, default deny, no Core."""
from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys
from uuid import uuid4

import pytest

from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.run.management_peer_authority import CurrentManagementPeerAuthority
from test.test_platform_service_session import provision

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


def request(platform_id, generation):
    now = datetime.now(timezone.utc)
    return json.dumps({
        "schema": "aegis.platform.management.read.v1",
        "protocol": "1.0",
        "request_id": "req:security",
        "target_platform_id": platform_id,
        "expected_generation": generation,
        "operation": "platform.status",
        "created_at": (now - timedelta(seconds=1)).isoformat(),
        "deadline": (now + timedelta(seconds=5)).isoformat(),
    }).encode("utf-8") + b"\n"


@pytest.mark.skipif(not LINUX, reason="actual AF_UNIX host only")
def test_service_binds_os_socket_and_unenrolled_peer_receives_only_eof(tmp_path):
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256
    ) as session:
        status = session.status()
        assert status["management_listening"] is True
        path = status["management_endpoint"]
        assert path and os.path.exists(path)
        assert os.stat(path).st_mode & 0o077 == 0
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(path)
            client.sendall(request(status["platform_id"], status["generation"]))
            assert client.recv(128) == b""
        assert session.status()["core_started"] is False
    assert not os.path.exists(path)
    assert not list(tmp_path.rglob("sofia.db"))


@pytest.mark.skipif(not LINUX, reason="actual AF_UNIX host only")
def test_service_health_refuses_replaced_management_socket_even_when_worker_alive(
        tmp_path, monkeypatch):
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as session:
        healthy = session.status()
        assert healthy["management_listening"] is True
        listener = session._management_listener
        assert listener is not None
        assert session._management_thread.is_alive()
        # A removed/replaced OS endpoint must not be reported as healthy
        # merely because the serving thread is still running.
        monkeypatch.setattr(
            listener, "_require_owned_endpoint",
            lambda: (_ for _ in ()).throw(
                PermissionError("management endpoint replaced or unsafe"),
            ),
        )
        with pytest.raises(PermissionError, match="endpoint replaced"):
            session.status()
        assert session._management_thread.is_alive()
    assert session.lease is None


@pytest.mark.skipif(not LINUX, reason="actual AF_UNIX host only")
def test_service_restart_rotates_endpoint_and_fences_generation(tmp_path):
    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256
    ) as first:
        old = first.status()
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256
    ) as second:
        new = second.status()
        assert new["generation"] > old["generation"]
        assert old["management_endpoint"] != new["management_endpoint"]
        assert not os.path.exists(old["management_endpoint"])


def test_grant_authorizer_requires_real_safe_store_and_exact_proof(tmp_path):
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    authority = CurrentManagementPeerAuthority(
        permissions, platform_id=current.identity.canonical_uuid,
    )
    assert authority("unix:uid:1000:gid:1000", "platform.status") is None
    assert authority("windows:sid:S-1-5-18", "platform.status") is None
    assert authority("unix:uid:1000:gid:1000", "module.remove") is None
    with pytest.raises(TypeError):
        CurrentManagementPeerAuthority(object(), platform_id=current.identity.canonical_uuid)


def test_authorizer_rereads_proven_grants_and_disallows_wildcard(tmp_path, monkeypatch):
    from sofia.platform.safe.permissions import StandingPermissionGrant
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    platform_id = current.identity.canonical_uuid
    now = datetime.now(timezone.utc)
    def grant(scope, revoked=False, proven=True):
        return StandingPermissionGrant(
            grant_id=str(uuid4()), capability="platform.management.read",
            scope=scope, granted_by="person:sparks",
            granted_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=1),
            revoked_at=now if revoked else None,
            owner_authenticated=proven,
        )
    exact = {
        "platform_id": platform_id,
        "peer": "unix:uid:1000:gid:1000",
        "operation": "platform.status",
    }
    state_now = {"current": (grant(exact),)}
    monkeypatch.setattr(permissions, "grants", lambda **_: state_now["current"])
    authority = CurrentManagementPeerAuthority(
        permissions, platform_id=platform_id, clock=lambda: now
    )
    assert authority("unix:uid:1000:gid:1000", "platform.status") == frozenset()
    state_now["current"] = (grant(exact, revoked=True),)
    assert authority("unix:uid:1000:gid:1000", "platform.status") is None
    state_now["current"] = (grant(exact, proven=False),)
    assert authority("unix:uid:1000:gid:1000", "platform.status") is None
    state_now["current"] = (grant({"peer": exact["peer"]}),)
    assert authority("unix:uid:1000:gid:1000", "platform.status") is None


def test_windows_operator_acl_requires_exact_current_attended_grant(tmp_path, monkeypatch):
    from sofia.platform.safe.permissions import StandingPermissionGrant
    from sofia.platform.run.management_windows_pipe import ManagementWindowsPipeListener

    identity, current, state = provision(tmp_path)
    store = PermissionStore(state)
    now = datetime.now(timezone.utc)
    pinned = current.identity.canonical_uuid
    sid = "S-1-5-21-1234-5678-9012-1235"
    scope = {"platform_id": pinned, "peer": "windows:sid:" + sid,
             "operation": "platform.status"}

    def exact_grant(scope, *, revoked=False, proven=True):
        return StandingPermissionGrant(
            grant_id=str(uuid4()), capability="platform.management.read",
            scope=scope, granted_by="person:sparks",
            granted_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(minutes=5),
            revoked_at=now if revoked else None,
            owner_authenticated=proven,
        )

    entries = []
    monkeypatch.setattr(store, "grants", lambda **_: tuple(entries))
    authority = CurrentManagementPeerAuthority(
        store, platform_id=pinned, clock=lambda: now,
    )
    assert authority.enrolled_windows_operator_sid() is None
    entries.append(exact_grant(scope))
    assert authority.enrolled_windows_operator_sid() == sid
    ManagementWindowsPipeListener(
        "AegisUnitTest", dispatch=lambda *_a, **_k: {},
        enrolled_operator_sid=authority.enrolled_windows_operator_sid(),
    )
    entries[:] = [exact_grant(scope, revoked=True)]
    assert authority.enrolled_windows_operator_sid() is None
    entries[:] = [exact_grant(scope, proven=False)]
    assert authority.enrolled_windows_operator_sid() is None
    entries[:] = [exact_grant({**scope, "peer": "windows:sid:S-1-5-32-544"})]
    with pytest.raises(PermissionError, match="operator principal"):
        authority.enrolled_windows_operator_sid()
    entries[:] = [
        exact_grant(scope),
        exact_grant({**scope, "peer": "windows:sid:S-1-5-21-1234-5678-9012-5678"}),
    ]
    with pytest.raises(PermissionError, match="multiple operator"):
        authority.enrolled_windows_operator_sid()
    for denied in ("S-1-5-18", "S-1-5-32-544", "S-1-1-0", "Administrators"):
        with pytest.raises(PermissionError):
            ManagementWindowsPipeListener(
                "AegisTest", dispatch=lambda *_a, **_k: {},
                enrolled_operator_sid=denied,
            )


def test_real_owner_signed_platform_grant_then_revocation_fails_closed(tmp_path):
    from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    peer = "unix:uid:20100:gid:20101"
    scope = {"platform_id": current.identity.canonical_uuid,
             "peer": peer, "operation": "platform.status"}
    authority = CurrentManagementPeerAuthority(
        permissions, platform_id=current.identity.canonical_uuid,
    )
    assert authority(peer, "platform.status") is None
    signed = grant_with_signed_owner(
        permissions, "platform.management.read", scope=scope,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert authority(peer, "platform.status") == frozenset()
    assert authority("unix:uid:20100:gid:999", "platform.status") is None
    assert authority(peer, "module.remove") is None
    revoke_with_signed_owner(permissions, signed.grant_id)
    assert authority(peer, "platform.status") is None


def test_actual_software_approval_rotation_revokes_live_platform_permission(tmp_path, monkeypatch):
    """Real salt+scrypt proof and SAFE ledger; test-only OS SID injection."""
    from sofia.platform.safe import owner_secret
    from sofia.platform.safe.owner_secret import OwnerSecretStore
    from sofia.platform.safe.execution_approval import (
        ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
    )
    from sofia.platform.safe.permissions import standing_grant_parameters

    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-FAKE-TEST-ONLY",
    )
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    software = OwnerSecretStore(state)
    software.enroll("11" * 32)
    peer = "windows:sid:S-1-5-21-555-666-777-1001"
    scope = {"platform_id": current.identity.canonical_uuid,
             "peer": peer, "operation": "platform.status"}
    moment = datetime.now(timezone.utc)
    grant_id = str(uuid4())
    expiry = moment + timedelta(minutes=5)
    fp = execution_fingerprint(
        "safe.permission.standing.grant",
        standing_grant_parameters(
            "platform.management.read", scope=scope,
            grant_id=grant_id, expires_at=expiry,
        ),
    )
    proof = software.authenticate("11" * 32, action_fingerprint=fp)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="safe.permission.standing.grant",
        request_fingerprint=fp, approved_by="Sparks", approved_at=moment,
        expires_at=expiry,
    )
    ExecutionApprovalVerifier(state).record(
        approval, authentication_event_id=proof,
    )
    permissions.grant(
        "platform.management.read", scope=scope, grant_id=grant_id,
        expires_at=expiry, now=moment, approval_id=approval.approval_id,
    )
    authority = CurrentManagementPeerAuthority(
        permissions, platform_id=current.identity.canonical_uuid,
    )
    assert authority(peer, "platform.status") == frozenset()
    software.rotate("11" * 32, "22" * 32)
    assert authority(peer, "platform.status") is None
    with pytest.raises(PermissionError):
        software.authenticate("11" * 32, action_fingerprint=fp)


@pytest.mark.skipif(not LINUX, reason="Linux systemd runtime boundary only")
def test_external_socket_never_uses_arbitrary_runtime_directory(tmp_path, monkeypatch):
    identity, current, state = provision(tmp_path)
    directory = tmp_path / "world"
    directory.mkdir(mode=0o777)
    directory.chmod(0o777)
    monkeypatch.setenv("RUNTIME_DIRECTORY", str(directory))
    with pytest.raises(PermissionError, match="unreviewed"):
        PlatformServiceSession(
            identity.home, state, current.identity.canonical_uuid,
            current.public_key_sha256,
        )
    assert not list(directory.iterdir())
    # A rejected runtime directory must release the process lease/lock.
    monkeypatch.delenv("RUNTIME_DIRECTORY")
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as session:
        assert session.status()["core_started"] is False


@pytest.mark.skipif(not LINUX, reason="Debian systemd runtime policy")
def test_systemd_runtime_policy_preserves_b_private_0700_without_group_enrollment(monkeypatch):
    import grp
    import stat
    from types import SimpleNamespace
    from sofia.platform.run.platform_service import systemd_management_operator_group

    uid, gid = os.geteuid(), os.getegid()
    parent = lambda mode, owner=uid, group=gid: SimpleNamespace(
        st_mode=stat.S_IFDIR | mode, st_uid=owner, st_gid=group,
    )
    # Team B's current /run/aegis-platform 0700 must not be rejected
    # or silently widened into proposed cross-user group access.
    monkeypatch.setattr(
        grp, "getgrnam",
        lambda *_: pytest.fail("private mode must not resolve operator group"),
    )
    for runtime in ("/run/aegis", "/run/aegis-platform"):
        assert systemd_management_operator_group(
            runtime, parent(0o700), service_uid=uid, service_gid=gid,
        ) is None
    with pytest.raises(PermissionError, match="unreviewed"):
        systemd_management_operator_group(
            "/tmp/aegis", parent(0o700), service_uid=uid, service_gid=gid,
        )


@pytest.mark.skipif(not LINUX, reason="Debian explicit operator GID policy")
def test_systemd_external_group_requires_dedicated_identity_and_strict_mode(monkeypatch):
    import grp
    import stat
    from types import SimpleNamespace
    from sofia.platform.run.platform_service import systemd_management_operator_group

    uid, gid = os.geteuid(), os.getegid()
    parent = lambda mode, owner=uid, group=gid: SimpleNamespace(
        st_mode=stat.S_IFDIR | mode, st_uid=owner, st_gid=group,
    )
    monkeypatch.setattr(
        grp, "getgrnam",
        lambda name: SimpleNamespace(gr_gid=gid) if name == "aegis-mgmt" else None,
    )
    assert systemd_management_operator_group(
        "/run/aegis-platform", parent(0o750),
        service_uid=uid, service_gid=gid,
    ) == gid
    for mode in (0o751, 0o755, 0o770, 0o777, 0o600):
        with pytest.raises(PermissionError):
            systemd_management_operator_group(
                "/run/aegis-platform", parent(mode),
                service_uid=uid, service_gid=gid,
            )
    with pytest.raises(PermissionError):
        systemd_management_operator_group(
            "/run/aegis", parent(0o750),
            service_uid=uid, service_gid=gid,
        )
    for bad_parent in (parent(0o750, owner=uid+1), parent(0o750, group=gid+1)):
        with pytest.raises(PermissionError, match="not governed"):
            systemd_management_operator_group(
                "/run/aegis-platform", bad_parent,
                service_uid=uid, service_gid=gid,
            )
    monkeypatch.setattr(grp, "getgrnam", lambda _: SimpleNamespace(gr_gid=gid+1))
    with pytest.raises(PermissionError, match="installed management group"):
        systemd_management_operator_group(
            "/run/aegis-platform", parent(0o750),
            service_uid=uid, service_gid=gid,
        )


@pytest.mark.skipif(not LINUX, reason="Debian dedicated supplementary operator GID")
def test_systemd_external_group_separate_from_service_primary_gid(monkeypatch):
    import grp
    import stat
    from types import SimpleNamespace
    from sofia.platform.run.platform_service import systemd_management_operator_group

    service_uid, service_gid, mgmt_gid = 31041, 31041, 31044
    monkeypatch.setattr(
        grp, "getgrnam",
        lambda name: SimpleNamespace(gr_gid=mgmt_gid) if name == "aegis-mgmt" else None,
    )
    parent = lambda mode, gid=mgmt_gid: SimpleNamespace(
        st_mode=stat.S_IFDIR | mode, st_uid=service_uid, st_gid=gid,
    )
    assert systemd_management_operator_group(
        "/run/aegis-platform", parent(0o750),
        service_uid=service_uid, service_gid=service_gid,
        service_groups=(mgmt_gid,),
    ) == mgmt_gid
    # A secondary operator group is never implied by filesystem mode alone.
    with pytest.raises(PermissionError, match="installed management group"):
        systemd_management_operator_group(
            "/run/aegis-platform", parent(0o750),
            service_uid=service_uid, service_gid=service_gid,
            service_groups=(),
        )
    with pytest.raises(PermissionError, match="installed management group"):
        systemd_management_operator_group(
            "/run/aegis-platform", parent(0o750, gid=service_gid),
            service_uid=service_uid, service_gid=service_gid,
            service_groups=(mgmt_gid,),
        )
    with pytest.raises(PermissionError, match="private service runtime group"):
        systemd_management_operator_group(
            "/run/aegis-platform", parent(0o700),
            service_uid=service_uid, service_gid=service_gid,
            service_groups=(mgmt_gid,),
        )
