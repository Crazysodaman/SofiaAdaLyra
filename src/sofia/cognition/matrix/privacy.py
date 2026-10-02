"""Principal/audience privacy projection for the message matrix."""
from __future__ import annotations

from sofia.social.model import AudienceKind, PrincipalContext

from .model import PrivacyProjectionPlan


class MatrixPrivacyPlanner:
    """Project trusted authenticated scope without creating private grants."""

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
        return PrivacyProjectionPlan(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            audience_kind=principal.audience_kind.value,
            allow_relationship_scope=True,
            allow_audience_scope=True,
            allow_historical_private_scope=private,
            allow_private_presentation_candidate=private,
            reason=(
                "authenticated principal/audience scope is eligible; "
                "underlying stores and private grants remain authoritative"
            ),
        )
