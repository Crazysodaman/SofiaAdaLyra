from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AudienceKind(Enum):
    PRIVATE = "private"
    SHARED = "shared"
    SYSTEM = "system"


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
