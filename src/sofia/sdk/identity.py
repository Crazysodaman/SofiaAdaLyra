"""Authority-free canonical Aegis identity and readable serial contracts.

Parsing an identity does not authenticate it. Allocation, key binding,
installation persistence and recovery belong to the Platform authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping
from uuid import UUID


IDENTITY_SCHEMA = "aegis.identity.v1"
_UUID_TEXT = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", re.ASCII)
_SERIAL = re.compile(r"AEG-([PC])-([0-9A-F]{8})-([0-9A-F]{8})-([0-9A-F]{8})-([0-9A-F]{8})", re.ASCII | re.IGNORECASE)


class IdentityKind(str, Enum):
    PLATFORM = "platform"
    CORE = "core"


@dataclass(frozen=True, slots=True)
class AegisIdentity:
    """Immutable typed UUID projection, independent of mutable display names.

    UUID bytes are never truncated, hashed or regenerated during conversion.
    Even a valid projection supplies no trust, permissions or writer authority.
    """

    kind: IdentityKind
    identity_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.kind, IdentityKind):
            raise TypeError("kind must be IdentityKind")
        if not isinstance(self.identity_id, UUID):
            raise TypeError("identity_id must be UUID")

    @property
    def canonical_uuid(self) -> str:
        return str(self.identity_id)

    @property
    def serial(self) -> str:
        prefix = "P" if self.kind is IdentityKind.PLATFORM else "C"
        digits = self.identity_id.hex.upper()
        groups = "-".join(digits[index:index + 8] for index in range(0, 32, 8))
        return f"AEG-{prefix}-{groups}"

    @classmethod
    def from_uuid_text(cls, kind: IdentityKind, value: str) -> AegisIdentity:
        """Accept only full hyphenated UUID text; normalize its hex case."""
        if not isinstance(value, str) or _UUID_TEXT.fullmatch(value) is None:
            raise ValueError("identity UUID must have full 8-4-4-4-12 hexadecimal form")
        return cls(kind, UUID(value))

    @classmethod
    def from_serial(cls, value: str) -> AegisIdentity:
        """Decode serial v1, permitting ASCII case normalization only."""
        if not isinstance(value, str):
            raise ValueError("identity serial must be text")
        match = _SERIAL.fullmatch(value)
        if match is None:
            raise ValueError("unsupported or malformed Aegis identity serial")
        kind = IdentityKind.PLATFORM if match[1].upper() == "P" else IdentityKind.CORE
        return cls(kind, UUID(hex="".join(match.groups()[1:])))

    def to_payload(self) -> dict[str, str]:
        return {
            "schema": IDENTITY_SCHEMA,
            "kind": self.kind.value,
            "uuid": self.canonical_uuid,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> AegisIdentity:
        """Strictly decode a versioned inert projection, never credentials."""
        if not isinstance(payload, Mapping):
            raise TypeError("identity payload must be a mapping")
        if set(payload) != {"schema", "kind", "uuid"}:
            raise ValueError("identity payload requires exactly schema, kind and uuid")
        if payload["schema"] != IDENTITY_SCHEMA:
            raise ValueError("unsupported Aegis identity schema")
        try:
            kind = IdentityKind(payload["kind"])
        except (TypeError, ValueError) as exc:
            raise ValueError("unsupported Aegis identity kind") from exc
        return cls.from_uuid_text(kind, payload["uuid"])
