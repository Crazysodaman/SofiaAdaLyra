"""Owner-private gate for sexual interaction semantics.

This gate controls whether the private Sofía application may process sexual
interaction context at all. It does not establish consent, preference, arousal,
desire, or permission for any particular contact.
"""
from __future__ import annotations

from dataclasses import dataclass
import os

from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID


_ENV = "SOFIA_PRIVATE_ADULT_INTERACTIONS"


@dataclass(frozen=True, slots=True)
class PrivateInteractionGrant:
    principal_id: str
    owner_verified: bool
    private_session: bool
    adult_private_use_enabled: bool
    external_stop_active: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id required")
        if any(
            type(value) is not bool
            for value in (
                self.owner_verified,
                self.private_session,
                self.adult_private_use_enabled,
                self.external_stop_active,
            )
        ):
            raise TypeError("private interaction grant flags must be booleans")

    @property
    def allowed(self) -> bool:
        return (
            self.principal_id == SPARKS_PRINCIPAL_ID
            and self.owner_verified
            and self.private_session
            and self.adult_private_use_enabled
            and not self.external_stop_active
        )

    def require(self) -> None:
        if not self.allowed:
            raise PermissionError(
                "private adult interaction context is not enabled for this session"
            )


def _enabled() -> bool:
    value = os.environ.get(_ENV, "").strip().lower()
    if value in ("", "0", "false", "off"):
        return False
    if value in ("1", "true", "on"):
        return True
    raise ValueError(
        f"{_ENV} must be 1 or 0 (also accepts true/false)"
    )


def private_interaction_grant(
    principal: PrincipalContext | None,
    *,
    external_stop_active: bool = False,
) -> PrivateInteractionGrant:
    if principal is not None and not isinstance(principal, PrincipalContext):
        raise TypeError("principal must be PrincipalContext or None")
    if type(external_stop_active) is not bool:
        raise TypeError("external_stop_active must be boolean")
    return PrivateInteractionGrant(
        principal_id=(
            principal.principal_id if principal is not None else "unbound"
        ),
        owner_verified=(
            principal is not None
            and principal.principal_id == SPARKS_PRINCIPAL_ID
        ),
        private_session=(
            principal is not None
            and principal.audience_kind is AudienceKind.PRIVATE
        ),
        adult_private_use_enabled=_enabled(),
        external_stop_active=external_stop_active,
    )
