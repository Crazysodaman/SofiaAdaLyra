"""Fresh Platform-local SAFE owner enrollment for read-only OS peers.

No self-enrollment. All approvals/grants are created by the existing SAFE
PermissionStore with one-use authenticated owner approval. Grant payload must
match this exact Platform ID, OS-derived peer and reviewed read operation.
A bare UID/SID or an unverified row never admits a management request.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sofia.platform.config.settings_authority import SettingsOwner
from sofia.platform.safe.permissions import PermissionStore

CAPABILITY = "platform.management.read"
_ALLOWED = frozenset({"platform.status"})
_SCOPE = frozenset({"platform_id", "peer", "operation"})


class CurrentManagementPeerAuthority:
    """Re-read SAFE grants and current proof on every admission and recheck."""

    def __init__(
        self,
        permissions: PermissionStore,
        *,
        platform_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(permissions, PermissionStore):
            raise TypeError("real SAFE PermissionStore required")
        if not isinstance(platform_id, str) or not platform_id:
            raise ValueError("pinned Platform ID required")
        self._permissions = permissions
        self._platform_id = platform_id
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def __call__(self, authenticated_peer: str, operation: str) -> frozenset[SettingsOwner] | None:
        if (not isinstance(authenticated_peer, str) or not authenticated_peer
                or not (authenticated_peer.startswith("unix:uid:")
                        or authenticated_peer.startswith("windows:sid:"))
                or operation not in _ALLOWED):
            return None
        moment = self._clock()
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise PermissionError("SAFE authorization clock unavailable")
        expected = {
            "platform_id": self._platform_id,
            "peer": authenticated_peer,
            "operation": operation,
        }
        # PermissionStore.grants() re-joins current consumed owner proof and
        # active credential/secret version. Revocation, expiry or secret
        # rotation invalidates old approvals rather than reusing snapshots.
        for grant in self._permissions.grants(active_only=False):
            if (grant.capability == CAPABILITY
                    and isinstance(grant.scope, dict)
                    and set(grant.scope) == _SCOPE
                    and grant.matches(expected, now=moment)):
                return frozenset()
        return None
