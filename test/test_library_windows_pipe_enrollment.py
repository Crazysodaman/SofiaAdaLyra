"""D028 Windows operator ACL parity: native pipe reads retain owner grants.

These are cross-platform pure principal policies. Actual Windows token
impersonation, SID account type and installed DACL require native host tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.run.library_read_authority import (
    CurrentLibraryReadPeerAuthority, CATALOG_OPERATION,
)
from sofia.platform.run.platform_service import select_enrolled_windows_pipe_sid
from sofia.platform.safe.permissions import PermissionStore
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
from test.test_platform_service_session import provision

SID = "S-1-5-21-1234-5678-9012-1235"
OTHER = "S-1-5-21-1234-5678-9012-1236"


def test_library_only_windows_operator_has_single_owner_enrolled_acl(tmp_path):
    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    authority = CurrentLibraryReadPeerAuthority(
        permissions, platform_id=current.identity.canonical_uuid,
    )
    assert authority.enrolled_windows_operator_sid() is None
    scope = {
        "platform_id": current.identity.canonical_uuid,
        "peer": "windows:sid:" + SID,
        "operation": CATALOG_OPERATION,
    }
    approved = grant_with_signed_owner(
        permissions, "platform.library.read", scope=scope,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert authority.enrolled_windows_operator_sid() == SID
    assert select_enrolled_windows_pipe_sid(None, SID) == SID
    assert select_enrolled_windows_pipe_sid(SID, SID) == SID
    assert authority(scope["peer"], CATALOG_OPERATION) is True
    assert authority(scope["peer"], "platform.status") is False
    revoke_with_signed_owner(permissions, approved.grant_id)
    assert authority.enrolled_windows_operator_sid() is None
    assert authority(scope["peer"], CATALOG_OPERATION) is False


@pytest.mark.parametrize("management,library", [
    (SID, OTHER), (SID, "S-1-5-32-544"),
    ("S-1-5-18", None), (None, "S-1-5-11"),
    (None, "S-1-1-0"),
])
def test_library_pipe_refuses_conflicting_or_group_operator_acl(management, library):
    with pytest.raises(PermissionError):
        select_enrolled_windows_pipe_sid(management, library)


def test_windows_pipe_unenrolled_operator_has_no_client_sid():
    assert select_enrolled_windows_pipe_sid(None, None) is None
