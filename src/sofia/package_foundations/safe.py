"""PKG-SAFE: offline fail-closed preflight; not an identity verifier or executor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuthorizationSnapshot:
    actor_authenticated: bool = False
    scoped_grant_verified: bool = False
    revoked: bool = True
    stop_active: bool = True
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for field in ('actor_authenticated', 'scoped_grant_verified', 'revoked', 'stop_active'):
            if not isinstance(getattr(self, field), bool):
                raise TypeError(f'{field} must be boolean.')
        if self.expires_at is not None and (
            self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None
        ):
            raise ValueError('Expiry must be timezone-aware.')

    def passes_preflight(self, now: datetime) -> bool:
        """Necessary conditions only: issuer, domain and execution checks still required."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('Evaluation time must be timezone-aware.')
        return (self.actor_authenticated and self.scoped_grant_verified
                and not self.revoked and not self.stop_active
                and self.expires_at is not None and now < self.expires_at)
