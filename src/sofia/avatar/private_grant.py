"""Trusted host resolution for private AVATAR presentation access."""
from __future__ import annotations

from pathlib import Path

from sofia.safe.operator_stop import OperatorStopStore
from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID

from .presentation import PrivatePresentationGrant


class PrivatePresentationGrantResolver:
    """Build one grant from trusted host/session facts, never from chat prose."""

    def __init__(
        self,
        *,
        state_path: Path | str,
        adult_verified: bool = False,
        operator_stop_store: OperatorStopStore | None = None,
    ) -> None:
        if type(adult_verified) is not bool:
            raise TypeError("adult_verified must be bool")
        if operator_stop_store is not None and not isinstance(
            operator_stop_store,
            OperatorStopStore,
        ):
            raise TypeError(
                "operator_stop_store must be OperatorStopStore or None"
            )
        # Kept only for constructor compatibility. Durable PermissionStore
        # authority is canonical and legacy configuration may never widen it.
        self._legacy_adult_verified = adult_verified
        self._permission_store = PermissionStore(state_path)
        self._operator_stop_store = (
            operator_stop_store or OperatorStopStore(state_path)
        )
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        """Return the latest fail-closed host-evidence lookup failure."""
        return self._last_error

    def resolve(
        self,
        *,
        principal: PrincipalContext | None,
        explicit_current_opt_in: bool,
    ) -> PrivatePresentationGrant | None:
        if principal is not None and not isinstance(
            principal,
            PrincipalContext,
        ):
            raise TypeError("principal must be PrincipalContext or None")
        if type(explicit_current_opt_in) is not bool:
            raise TypeError("explicit_current_opt_in must be bool")

        owner_verified = (
            principal is not None
            and principal.principal_id == SPARKS_PRINCIPAL_ID
        )
        private_session = (
            principal is not None
            and principal.audience_kind is AudienceKind.PRIVATE
        )
        authority = self._permission_store.private_adult_authority()
        adult_verified = authority.adult_avatar
        if not (
            adult_verified
            and authority.private_chat
            and owner_verified
            and private_session
            and explicit_current_opt_in
        ):
            self._last_error = None
            return None

        try:
            external_stop_active = self._operator_stop_store.current().active
        except Exception as exc:
            self._last_error = type(exc).__name__
            return None
        self._last_error = None

        grant = PrivatePresentationGrant(
            adult_verified=adult_verified,
            owner_verified=owner_verified,
            private_session=private_session,
            explicit_current_opt_in=explicit_current_opt_in,
            external_stop_active=external_stop_active,
        )
        try:
            grant.require()
        except PermissionError:
            return None
        return grant
