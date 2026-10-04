"""Principal/audience privacy projection for the message matrix."""
from __future__ import annotations

from pathlib import Path

from sofia.safe.permissions import PermissionStore
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID

from .model import PrivacyProjectionPlan


class MatrixPrivacyPlanner:
    """Project trusted authenticated scope without creating private grants."""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self._permission_store = (
            None if state_path is None else PermissionStore(state_path)
        )

    def plan(
        self,
        principal: PrincipalContext | None,
    ) -> PrivacyProjectionPlan:
        if principal is None:
            return PrivacyProjectionPlan(
                principal_id=None,
                audience_id=None,
                audience_kind=None,
                allow_relationship_scope=False,
                allow_audience_scope=False,
                allow_historical_private_scope=False,
                allow_private_presentation_candidate=False,
                reason=(
                    "no authenticated principal is bound to this turn; "
                    "person-scoped state fails closed"
                ),
            )
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext or None")

        private = principal.audience_kind is AudienceKind.PRIVATE
        private_authorized = private
        if (
            self._permission_store is not None
            and principal.principal_id == SPARKS_PRINCIPAL_ID
        ):
            private_authorized = (
                private
                and self._permission_store.private_adult_authority().private_chat
            )

        return PrivacyProjectionPlan(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            audience_kind=principal.audience_kind.value,
            allow_relationship_scope=True,
            allow_audience_scope=True,
            allow_historical_private_scope=private_authorized,
            allow_private_presentation_candidate=private_authorized,
            reason=(
                "authenticated principal/audience scope is eligible; "
                "owner private-state access also follows durable permission "
                "authority, while underlying stores and grants remain authoritative"
            ),
        )
