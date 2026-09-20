"""Engineering 22F: explicit, exact-scope, revocable local authorization.

Only locally approved grants can authorize a requested node/capability/operation.
No enrollment, advertised capability, prompt, or connectivity grants permission.
Grants are in-memory and must be reapproved after process restart.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sofia.distributed.capabilities import _aware, _identifier


@dataclass(frozen=True)
class RemoteGrant:
    grant_id: UUID
    node_id: UUID
    capability: str
    operation: str
    approved_by: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, UUID) or not isinstance(self.node_id, UUID):
            raise TypeError("Grant identifiers must be UUIDs.")
        _identifier(self.capability, "Grant capability")
        _identifier(self.operation, "Grant operation")
        if not isinstance(self.approved_by, str) or not self.approved_by.strip():
            raise ValueError("Grant must identify its human approver.")
        _aware(self.expires_at, "Grant expires_at")


class RemoteAuthorization:
    """No implicit grants; explicit user approval is external to this object."""

    def __init__(self) -> None:
        self._grants: dict[UUID, RemoteGrant] = {}

    def add_approved_grant(self, grant: RemoteGrant) -> None:
        if not isinstance(grant, RemoteGrant):
            raise TypeError("grant must be a RemoteGrant.")
        if grant.grant_id in self._grants:
            raise ValueError("Grant ID already exists; implicit renewal is forbidden.")
        self._grants[grant.grant_id] = grant

    def revoke(self, grant_id: UUID) -> None:
        if not isinstance(grant_id, UUID):
            raise TypeError("grant_id must be a UUID.")
        self._grants.pop(grant_id, None)

    def permits(self, grant_id: UUID, *, node_id: UUID, capability: str,
                operation: str, now: datetime) -> bool:
        _aware(now, "now")
        if not isinstance(grant_id, UUID) or not isinstance(node_id, UUID):
            return False
        grant = self._grants.get(grant_id)
        return bool(grant is not None and grant.node_id == node_id
                    and grant.capability == capability and grant.operation == operation
                    and now < grant.expires_at)
