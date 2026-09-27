"""Provider-neutral authenticated principal and audience identity."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


class PrincipalKind(str, Enum):
    HUMAN = "human"
    SERVICE = "service"
    HOST = "host"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Identity established outside model-generated content."""

    principal_id: str
    kind: PrincipalKind
    source: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.principal_id, "principal_id")
        if not isinstance(self.kind, PrincipalKind):
            raise TypeError("kind must be a PrincipalKind")
        _identifier(self.source, "source")
        if self.display_name is not None:
            if (
                not isinstance(self.display_name, str)
                or not self.display_name.strip()
                or len(self.display_name) > 160
            ):
                raise ValueError("display_name must be bounded non-empty text")


class AudienceScope(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    PUBLIC = "public"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Audience:
    audience_id: str
    scope: AudienceScope
    member_principal_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.audience_id, "audience_id")
        if not isinstance(self.scope, AudienceScope):
            raise TypeError("scope must be an AudienceScope")
        if not isinstance(self.member_principal_ids, tuple):
            raise TypeError("member_principal_ids must be a tuple")
        for member in self.member_principal_ids:
            _identifier(member, "member_principal_id")
        if len(set(self.member_principal_ids)) != len(
            self.member_principal_ids
        ):
            raise ValueError("audience members must be distinct")
        if (
            self.scope is AudienceScope.PRIVATE
            and len(self.member_principal_ids) != 1
        ):
            raise ValueError(
                "private audience requires exactly one human/service member"
            )
