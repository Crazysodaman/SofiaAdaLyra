"""Explicit audience scopes and active-principal admission for memory recall."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from sofia.core.social.model import AudienceKind, PrincipalContext


class MemoryAudienceScope(str, Enum):
    OWNER = "owner"
    PRIVATE = "private"
    GUEST = "guest"


def classify_memory_scope(
    principal: PrincipalContext,
    *,
    owner_principal_id: str,
) -> MemoryAudienceScope:
    """Map one authenticated principal to an explicit memory audience scope."""
    if not isinstance(principal, PrincipalContext):
        raise TypeError("principal must be a PrincipalContext")
    if principal.audience_kind is AudienceKind.SYSTEM:
        raise PermissionError("system audience carries no person-memory scope")
    if principal.audience_kind is AudienceKind.SHARED:
        return MemoryAudienceScope.GUEST
    if principal.principal_id == owner_principal_id:
        return MemoryAudienceScope.OWNER
    return MemoryAudienceScope.PRIVATE


@dataclass(frozen=True, slots=True)
class PrincipalGrant:
    principal_id: str
    audience_id: str
    audience_kind: AudienceKind
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id must be nonempty")
        if not isinstance(self.audience_id, str) or not self.audience_id.strip():
            raise ValueError("audience_id must be nonempty")
        if not isinstance(self.audience_kind, AudienceKind):
            raise TypeError("audience_kind must be an AudienceKind")
        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime):
                raise TypeError("expires_at must be a datetime or None")
            if (
                self.expires_at.tzinfo is None
                or self.expires_at.utcoffset() is None
            ):
                raise ValueError("expires_at must be timezone-aware")

    def is_active(self, *, at: datetime | None = None) -> bool:
        if self.expires_at is None:
            return True
        moment = at or datetime.now(timezone.utc)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        return moment.astimezone(timezone.utc) < self.expires_at.astimezone(
            timezone.utc
        )


class ActivePrincipalRegistry:
    """Exact principal/audience grant set; unknown and expired grants deny."""

    def __init__(self, grants: Iterable[PrincipalGrant]) -> None:
        self._grants = tuple(grants)
        if any(not isinstance(grant, PrincipalGrant) for grant in self._grants):
            raise TypeError("grants must contain PrincipalGrant instances")

    def require_active(
        self,
        principal: PrincipalContext,
        *,
        at: datetime | None = None,
    ) -> PrincipalGrant:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        for grant in self._grants:
            if (
                grant.principal_id == principal.principal_id
                and grant.audience_id == principal.audience_id
                and grant.audience_kind is principal.audience_kind
            ):
                if not grant.is_active(at=at):
                    raise PermissionError("memory principal grant has expired")
                return grant
        raise PermissionError("unknown memory principal/audience grant")
