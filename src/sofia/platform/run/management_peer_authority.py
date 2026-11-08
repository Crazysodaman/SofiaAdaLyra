"""Fresh Platform-local SAFE owner enrollment for read-only OS peers.

No self-enrollment. All approvals/grants are created by the existing SAFE
PermissionStore with one-use authenticated owner approval. Grant payload must
match this exact Platform ID, OS-derived peer and reviewed read operation.
A bare UID/SID or an unverified row never admits a management request.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re

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

    def enrolled_windows_operator_sid(self) -> str | None:
        """One *currently owner-approved* human user SID for the pipe DACL.

        This is only OS connection admission. Dispatch still checks live SAFE,
        STOP, exact Platform/operation scope and revocation on every request.
        No synthetic SID, group SID, or generic interactive-user ACL.
        Multiple active enrolled operators are refused until installer policy
        explicitly defines a reviewed multi-operator contract.
        """
        moment = self._clock()
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise PermissionError("SAFE authorization clock unavailable")
        operators: set[str] = set()
        for grant in self._permissions.grants(active_only=False):
            if (grant.capability != CAPABILITY
                    or not isinstance(grant.scope, dict)
                    or set(grant.scope) != _SCOPE
                    or grant.scope.get("platform_id") != self._platform_id
                    or grant.scope.get("operation") != "platform.status"
                    or not grant.matches(grant.scope, now=moment)):
                continue
            peer = grant.scope.get("peer")
            if not isinstance(peer, str) or not peer.startswith("windows:sid:"):
                continue
            sid = peer.removeprefix("windows:sid:")
            # Only individually enrolled local/domain *user* SIDs. System,
            # service accounts, Everyone, Administrators, Authenticated Users
            # and group SIDs cannot be nominated by this access contract.
            if re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", sid) is None:
                raise PermissionError("unsupported Windows operator principal")
            operators.add(sid)
            if len(operators) > 1:
                raise PermissionError("multiple operator SIDs require explicit installer policy")
        return next(iter(operators), None)
