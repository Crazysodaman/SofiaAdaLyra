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
