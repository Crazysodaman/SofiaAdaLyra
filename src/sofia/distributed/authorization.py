"""Engineering 22F: explicit, exact-scope, revocable local authorization.

Only locally approved grants can authorize a requested node/capability/operation.
No enrollment, advertised capability, prompt, or connectivity grants permission.
Production grants are persisted by DurableRemoteAuthorization; this module
defines the admission interface and immutable grant contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
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


class RemoteAuthorization(ABC):
    """Exact-scope admission interface; implementations own grant persistence."""

    @abstractmethod
    def add_approved_grant(self, grant: RemoteGrant) -> None:
        raise NotImplementedError

    @abstractmethod
    def revoke(self, grant_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def permits(self, grant_id: UUID, *, node_id: UUID, capability: str,
                operation: str, now: datetime) -> bool:
        raise NotImplementedError
