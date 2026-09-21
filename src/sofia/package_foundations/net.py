"""PKG-NET: offline scoped-grant validation, not transport or remote execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RemoteGrant:
    node_id: str
    capability: str
    expires_at: datetime
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.capability.strip():
            raise ValueError('A node and capability are required.')
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError('Expiration requires an aware timestamp.')

    def permits(self, *, node_id: str, capability: str, now: datetime) -> bool:
        """One necessary condition only; never sufficient for remote authorization."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Evaluation time must be aware.')
        return (not self.revoked and now < self.expires_at
                and node_id == self.node_id and capability == self.capability)
