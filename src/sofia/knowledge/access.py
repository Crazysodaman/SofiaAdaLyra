"""Audience/privacy boundary for knowledge sources and derived documents."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.social.principal import Audience, AuthenticatedPrincipal


class KnowledgeVisibility(str, Enum):
    PRIVATE = "private"
    AUDIENCE = "audience"
    SHARED = "shared"


@dataclass(frozen=True, slots=True)
class KnowledgeAccess:
    visibility: KnowledgeVisibility
    owner_principal_id: str | None = None
    audience_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.visibility, KnowledgeVisibility):
            raise TypeError("visibility must be KnowledgeVisibility")
        if self.visibility is KnowledgeVisibility.PRIVATE:
            if not self.owner_principal_id:
                raise ValueError("private knowledge requires owner_principal_id")
        if self.visibility is KnowledgeVisibility.AUDIENCE:
            if not self.audience_id:
                raise ValueError("audience knowledge requires audience_id")

    def permits(
        self,
        principal: AuthenticatedPrincipal | None,
        audience: Audience | None,
    ) -> bool:
        if self.visibility is KnowledgeVisibility.SHARED:
            return True
        if principal is None:
            return False
        if (
            self.visibility is KnowledgeVisibility.PRIVATE
            and principal.principal_id == self.owner_principal_id
        ):
            return True
        return (
            self.visibility is KnowledgeVisibility.AUDIENCE
            and audience is not None
            and audience.audience_id == self.audience_id
            and (
                not audience.member_principal_ids
                or principal.principal_id in audience.member_principal_ids
            )
        )
