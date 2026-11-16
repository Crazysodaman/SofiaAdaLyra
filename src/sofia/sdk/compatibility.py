"""Authority-free compatibility negotiation for the component wire protocol.

The existing wire protocol remains exactly ``1.0``.  This module adds an
explicit, deterministic negotiation surface for additive minor changes; an
unknown major, unsupported minor or missing critical field fails closed.

Nothing here authenticates a peer, grants authority or claims that two
installed components are compatible.  It only projects the reviewed protocol
rules that callers may enforce before decoding a contract envelope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts import ProtocolVersion, SDK_PROTOCOL_VERSION


WIRE_PROTOCOL = SDK_PROTOCOL_VERSION
MINIMUM_CRITICAL_FIELDS = frozenset({
    "authority",
    "destination",
    "payload_digest",
    "payload_type",
    "protocol",
    "source",
})


class CompatibilityError(ValueError):
    """Stable, language-neutral negotiation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ProtocolRange:
    """One reviewed major version and its explicitly supported minor range."""

    minimum: ProtocolVersion = WIRE_PROTOCOL
    maximum: ProtocolVersion = WIRE_PROTOCOL
    additive_minor: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.minimum, ProtocolVersion) or not isinstance(
            self.maximum, ProtocolVersion
        ):
            raise TypeError("protocol range requires typed versions")
        if self.minimum.major != self.maximum.major:
            raise ValueError("one range cannot span incompatible major versions")
        if self.maximum < self.minimum:
            raise ValueError("protocol maximum cannot precede minimum")
        if type(self.additive_minor) is not bool:
            raise TypeError("additive_minor must be bool")

    def contains(self, version: ProtocolVersion) -> bool:
        return (
            isinstance(version, ProtocolVersion)
            and version.major == self.minimum.major
            and self.minimum <= version <= self.maximum
        )


_LOCAL_RANGE = ProtocolRange()


def _coerce_version(value: object) -> ProtocolVersion:
    if isinstance(value, ProtocolVersion):
        return value
    if isinstance(value, str):
        try:
            return ProtocolVersion.parse(value)
        except (TypeError, ValueError) as exc:
            raise CompatibilityError(
                "malformed_protocol", "peer protocol must use MAJOR.MINOR"
            ) from exc
    if (
        type(value) is tuple
        and len(value) == 2
        and all(type(part) is int for part in value)
    ):
        try:
            return ProtocolVersion(value[0], value[1])
        except ValueError as exc:
            raise CompatibilityError(
                "malformed_protocol", "peer protocol is out of range"
            ) from exc
    raise CompatibilityError(
        "malformed_protocol", "peer protocol must be a version string or pair"
    )


def _required_field_names(required_fields: object) -> frozenset[str]:
    if isinstance(required_fields, Mapping):
        names = tuple(required_fields)
    elif isinstance(required_fields, (set, frozenset, list, tuple)):
        names = tuple(required_fields)
    else:
        raise CompatibilityError(
            "malformed_fields", "required fields must be a field collection"
        )
    if any(not isinstance(name, str) for name in names):
        raise CompatibilityError(
            "malformed_fields", "required fields must contain only names"
        )
    return frozenset(names)


def negotiate_protocol(
    peer_major_minor: object,
    required_fields: object,
    *,
    local_range: ProtocolRange = _LOCAL_RANGE,
    local_supports_additive_minor: bool = False,
    peer_supports_additive_minor: bool = False,
) -> ProtocolVersion:
    """Return the negotiated wire version or raise ``CompatibilityError``.

    Exact ``1.0`` is accepted by default.  A newer minor is accepted only when
    both the local range and the peer explicitly opt in to additive minor
    negotiation.  A different major version, malformed version, malformed field
    collection or missing minimum critical field fails closed.
    """
    if not isinstance(local_range, ProtocolRange):
        raise TypeError("local_range must be ProtocolRange")
    if (
        type(local_supports_additive_minor) is not bool
        or type(peer_supports_additive_minor) is not bool
    ):
        raise CompatibilityError(
            "malformed_fields", "additive-minor support must be bool"
        )
    if local_supports_additive_minor and not local_range.additive_minor:
        local_range = ProtocolRange(
            local_range.minimum,
            local_range.maximum,
            additive_minor=True,
        )
    peer = _coerce_version(peer_major_minor)
    fields = _required_field_names(required_fields)
    missing = MINIMUM_CRITICAL_FIELDS - fields
    if missing:
        raise CompatibilityError(
            "missing_critical_fields",
            "missing critical fields: " + ", ".join(sorted(missing)),
        )
    if peer.major != local_range.minimum.major:
        raise CompatibilityError(
            "unsupported_major", "peer protocol major version is incompatible"
        )
    if peer.minor < local_range.minimum.minor:
        raise CompatibilityError(
            "unsupported_minor", "peer protocol minor version is unsupported"
        )
    if peer.minor <= local_range.maximum.minor:
        return peer
    if local_range.additive_minor and peer_supports_additive_minor:
        return peer
    raise CompatibilityError(
        "unsupported_minor", "peer protocol minor version is unsupported"
    )


def compatibility_manifest() -> dict[str, object]:
    """Return the deterministic protocol projection; never a claim of parity."""
    return {
        "schema": "aegis.sdk.compatibility.v1",
        "wire_protocol": str(WIRE_PROTOCOL),
        "protocol_major": WIRE_PROTOCOL.major,
        "protocol_minor": WIRE_PROTOCOL.minor,
        "minimum_critical_fields": sorted(MINIMUM_CRITICAL_FIELDS),
        "additive_minor": False,
        "compatibility_claim": False,
        "inventory_only": True,
    }
