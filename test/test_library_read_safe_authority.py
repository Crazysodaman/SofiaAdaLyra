"""Native Library read grant lives in the existing real SAFE PermissionStore.

Synthetic disposable owner credentials only; not a production installation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.run.library_read_authority import (
    CATALOG_OPERATION, CurrentLibraryReadPeerAuthority,
)
from sofia.platform.safe.permissions import PermissionStore
from test.test_platform_service_session import provision
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner


def _scope(platform_id, peer):
    return {
        "platform_id": platform_id,
        "peer": peer,
        "operation": CATALOG_OPERATION,
    }


def test_real_safe_owner_grants_and_revokes_native_library_reader(tmp_path):
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    principal = "unix:uid:20100:gid:20101"
    operation = CATALOG_OPERATION
    authority = CurrentLibraryReadPeerAuthority(
        permissions, platform_id=current.identity.canonical_uuid,
    )
    assert authority(principal, operation) is False
    accepted = grant_with_signed_owner(
        permissions, "platform.library.read",
        scope=_scope(current.identity.canonical_uuid, principal),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert authority(principal, operation) is True
    assert authority("unix:uid:20100:gid:999", operation) is False
    assert authority(principal, "platform.status") is False
    assert authority(principal, "library.install.execute.v1") is False
    revoke_with_signed_owner(permissions, accepted.grant_id)
    assert authority(principal, operation) is False


def test_library_read_requires_exact_os_peer_scope_and_bounded_expiry(tmp_path):
    identity, current, state = provision(tmp_path)
    store = PermissionStore(state)
    scope = _scope(current.identity.canonical_uuid, "unix:uid:1001:gid:1002")
    now = datetime.now(timezone.utc)
    for malformed in (
        {**scope, "operation": "library.install.execute.v1"},
        {**scope, "peer": "arbitrary-string"},
        {**scope, "platform_id": ""},
        {**scope, "wildcard": True},
    ):
        with pytest.raises(PermissionError, match="Library read grant"):
            store.grant(
                "platform.library.read", scope=malformed,
                expires_at=now + timedelta(minutes=5),
                now=now, approval_id="not-real-approval",
            )
    for expiry in (None, now + timedelta(hours=2)):
        with pytest.raises(PermissionError, match="Library read grant"):
            store.grant(
                "platform.library.read", scope=scope,
                expires_at=expiry, now=now,
                approval_id="not-real-approval",
            )


def test_library_read_never_self_grants_on_scope_alone(tmp_path):
    identity, current, state = provision(tmp_path)
    store = PermissionStore(state)
    scope = _scope(current.identity.canonical_uuid, "unix:uid:1001:gid:1002")
    with pytest.raises(PermissionError):
        store.grant(
            "platform.library.read", scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            granted_by="person:sparks",
        )
    assert not any(
        item.capability == "platform.library.read"
        for item in store.grants(active_only=False)
    )
