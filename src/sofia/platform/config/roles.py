"""Mode-neutral Platform role configuration.

Roles describe which reviewed responsibilities this Platform installation may
attempt to serve.  They do not install a Core, enroll a peer, acquire a writer
lease, or grant any capability.  Effectful owners must still perform their
normal package, identity, SAFE, STOP, lease, and generation checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os


PLATFORM_ROLES_ENV = "SOFIA_PLATFORM_ROLES"


class PlatformRole(str, Enum):
    CORE_HOST = "CORE_HOST"
    CORE_LINK = "CORE_LINK"
    MODULE_HOST = "MODULE_HOST"
    STANDBY = "STANDBY"


@dataclass(frozen=True, slots=True)
class PlatformRoleConfiguration:
    """Reviewed composable roles for one Platform instance.

    The integrated compatibility installation defaults to CORE_HOST plus
    MODULE_HOST.  A future split Platform package must set its roles
    explicitly and can use CORE_LINK/MODULE_HOST without importing Core.
    """

    roles: tuple[PlatformRole, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported Platform role schema version")
        if not isinstance(self.roles, tuple) or not self.roles:
            raise ValueError("at least one Platform role is required")
        if any(not isinstance(role, PlatformRole) for role in self.roles):
            raise TypeError("roles must contain PlatformRole values")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("Platform roles must be unique")
        if (
            PlatformRole.STANDBY in self.roles
            and PlatformRole.CORE_HOST in self.roles
        ):
            raise ValueError(
                "STANDBY cannot be an acting CORE_HOST without an approved cutover"
            )

    @classmethod
    def integrated_compatibility(cls) -> "PlatformRoleConfiguration":
        return cls((PlatformRole.CORE_HOST, PlatformRole.MODULE_HOST))

    @classmethod
    def parse(cls, value: str) -> "PlatformRoleConfiguration":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Platform roles must be a nonempty comma-separated list")
        raw = tuple(part.strip() for part in value.split(","))
        if any(not part for part in raw):
            raise ValueError("Platform roles cannot contain empty entries")
        try:
            roles = tuple(PlatformRole(part) for part in raw)
        except ValueError as exc:
            raise ValueError("Platform roles contain an unsupported role") from exc
        return cls(roles)

    @classmethod
    def from_environment(cls) -> "PlatformRoleConfiguration":
        value = os.environ.get(PLATFORM_ROLES_ENV)
        if value is None:
            return cls.integrated_compatibility()
        return cls.parse(value)

    def supports(self, role: PlatformRole) -> bool:
        if not isinstance(role, PlatformRole):
            raise TypeError("role must be PlatformRole")
        return role in self.roles

    def require(self, role: PlatformRole) -> None:
        if not self.supports(role):
            raise PermissionError(
                f"Platform role {role.value} is not configured on this instance"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "companion.platform.roles.v1",
            "roles": [role.value for role in self.roles],
        }

