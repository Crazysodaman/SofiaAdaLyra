from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AudienceKind(Enum):
    PRIVATE = "private"
    SHARED = "shared"
    SYSTEM = "system"


class ScopeKind(Enum):
    GLOBAL = "global"
    RELATIONSHIP = "relationship"
    AUDIENCE = "audience"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class SocialScope:
    """Explicit storage/projection scope for person-sensitive state."""

    kind: ScopeKind
    principal_id: str | None = None
    audience_id: str | None = None
    audience_kind: AudienceKind | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeKind):
            raise TypeError("kind must be a ScopeKind")
        for name, value in (
            ("principal_id", self.principal_id),
            ("audience_id", self.audience_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{name} must be None or a nonempty string")
        if self.audience_kind is not None and not isinstance(
            self.audience_kind, AudienceKind
        ):
            raise TypeError("audience_kind must be an AudienceKind or None")

        if self.kind in (ScopeKind.GLOBAL, ScopeKind.SYSTEM):
            if any(
                value is not None
                for value in (
                    self.principal_id,
                    self.audience_id,
                    self.audience_kind,
                )
            ):
                raise ValueError(
                    "global/system scopes cannot carry principal or audience identity"
                )
        elif self.kind is ScopeKind.RELATIONSHIP:
            if self.principal_id is None:
                raise ValueError("relationship scope requires principal_id")
            if self.audience_id is not None or self.audience_kind is not None:
                raise ValueError(
                    "relationship scope is principal-wide, not audience-specific"
                )
        elif self.kind is ScopeKind.AUDIENCE:
            if (
                self.principal_id is None
                or self.audience_id is None
                or self.audience_kind is None
            ):
                raise ValueError(
                    "audience scope requires principal, audience, and audience kind"
                )

    @property
    def key(self) -> str:
        if self.kind is ScopeKind.RELATIONSHIP:
            return f"relationship:{self.principal_id}"
        if self.kind is ScopeKind.AUDIENCE:
            return (
                f"audience:{self.principal_id}:{self.audience_kind.value}:"
                f"{self.audience_id}"
            )
        return self.kind.value

    @classmethod
    def global_scope(cls) -> "SocialScope":
        return cls(ScopeKind.GLOBAL)

    @classmethod
    def system_scope(cls) -> "SocialScope":
        return cls(ScopeKind.SYSTEM)

    @classmethod
    def relationship(cls, principal_id: str) -> "SocialScope":
        return cls(ScopeKind.RELATIONSHIP, principal_id=principal_id)

    @classmethod
    def audience(cls, principal: "PrincipalContext") -> "SocialScope":
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        return cls(
            ScopeKind.AUDIENCE,
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            audience_kind=principal.audience_kind,
        )


@dataclass(frozen=True, slots=True)
class PrincipalContext:
    """
    Authenticated person/audience identity projected into one operation.

    display_name is conversational metadata only. principal_id is the stable
    authorization/storage key and must come from an authenticated boundary.
    """

    principal_id: str
    audience_id: str
    audience_kind: AudienceKind
    display_name: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("principal_id", self.principal_id),
            ("audience_id", self.audience_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if not isinstance(self.audience_kind, AudienceKind):
            raise TypeError("audience_kind must be an AudienceKind")
        if self.display_name is not None and (
            not isinstance(self.display_name, str)
            or not self.display_name.strip()
        ):
            raise ValueError(
                "display_name must be None or a nonempty string"
            )

    @property
    def relationship_scope(self) -> SocialScope:
        return SocialScope.relationship(self.principal_id)

    @property
    def audience_scope(self) -> SocialScope:
        return SocialScope.audience(self)
