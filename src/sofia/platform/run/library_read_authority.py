"""Canonical SAFE enrollment for local OS-authenticated Library reads.

No network listener, owner secret, token minting or publisher signer.
The caller identity comes only from the kernel Unix peer or independently
impersonated Windows named-pipe token. A request's claimed Platform ID is
never peer authentication. An absent/expired/revoked grant returns None,
causing EOF without disclosing even the existence of a catalog.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Callable

from sofia.platform.safe.permissions import PermissionStore

LIBRARY_READ_CAPABILITY = "platform.library.read"
CATALOG_OPERATION = "library.catalog.snapshot.v1"
_SCOPE = frozenset({"platform_id", "peer", "operation"})


class CurrentLibraryReadPeerAuthority:
    def __init__(
        self, permissions: PermissionStore, *,
        platform_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not isinstance(permissions, PermissionStore):
            raise TypeError("canonical SAFE PermissionStore required")
        if type(platform_id) is not str or not platform_id:
            raise ValueError("current installed Platform ID required")
        self.permissions = permissions
        self.platform_id = platform_id
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def __call__(self, authenticated_peer: str, operation: str) -> bool:
        if (type(authenticated_peer) is not str or not (
                authenticated_peer.startswith("unix:uid:")
                or authenticated_peer.startswith("windows:sid:"))
                or operation != CATALOG_OPERATION):
            return False
        now = self.clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise PermissionError("current SAFE Library enrollment clock required")
        expected = {
            "platform_id": self.platform_id,
            "peer": authenticated_peer,
            "operation": CATALOG_OPERATION,
        }
        for grant in self.permissions.grants(active_only=False):
            if (grant.capability == LIBRARY_READ_CAPABILITY
                    and isinstance(grant.scope, dict)
                    and set(grant.scope) == _SCOPE
                    and grant.matches(expected, now=now)):
                return True
        return False

    def enrolled_windows_operator_sid(self) -> str | None:
        """At most one real owner-enrolled individual user SID for pipe DACL.

        OS ACL selection is connection filtering, not permission to read a
        catalog. Every request still rechecks the live owner SAFE grant.
        """
        now = self.clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise PermissionError("Library read enrollment clock unavailable")
        operators: set[str] = set()
        for grant in self.permissions.grants(active_only=False):
            if (grant.capability != LIBRARY_READ_CAPABILITY
                    or type(grant.scope) is not dict
                    or set(grant.scope) != _SCOPE
                    or grant.scope.get("platform_id") != self.platform_id
                    or grant.scope.get("operation") != CATALOG_OPERATION
                    or not grant.matches(grant.scope, now=now)):
                continue
            peer = grant.scope.get("peer")
            if type(peer) is not str or not peer.startswith("windows:sid:"):
                continue
            sid = peer.removeprefix("windows:sid:")
            if re.fullmatch(r"S-1-5-21-(?:[0-9]+-){3}[0-9]+", sid) is None:
                raise PermissionError("unsupported Library operator principal")
            operators.add(sid)
            if len(operators) > 1:
                raise PermissionError("multiple Library operator SIDs require explicit installer policy")
        return next(iter(operators), None)
