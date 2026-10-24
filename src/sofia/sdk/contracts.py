"""Versioned, authority-free contracts shared by Platform, Core and modules.

These values are safe to serialize across a process boundary.  They project
identity and existing authority; constructing one never authenticates a
principal, grants a capability, or permits an effect.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Mapping


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PAYLOAD_TYPE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}\.v[1-9][0-9]*$")


def _utc(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _exact(document: object, keys: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(document, Mapping) or set(document) != keys:
        raise ValueError(f"{label} must contain exactly the reviewed fields")
    return document


def _time(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO timestamp")
    try:
        return _utc(datetime.fromisoformat(value), label)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc


@dataclass(frozen=True, order=True, slots=True)
class ProtocolVersion:
    major: int
    minor: int

    def __post_init__(self) -> None:
        if type(self.major) is not int or not 1 <= self.major <= 65_535:
            raise ValueError("protocol major must be in 1..65535")
        if type(self.minor) is not int or not 0 <= self.minor <= 65_535:
            raise ValueError("protocol minor must be in 0..65535")

    @classmethod
    def parse(cls, value: str) -> "ProtocolVersion":
        if not isinstance(value, str) or not re.fullmatch(
            r"[1-9][0-9]{0,4}\.(?:0|[1-9][0-9]{0,4})", value
        ):
            raise ValueError("protocol version must use MAJOR.MINOR")
        major, minor = value.split(".")
        return cls(int(major), int(minor))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


SDK_PROTOCOL_VERSION = ProtocolVersion(1, 0)


@dataclass(frozen=True, slots=True)
class ProtocolVersionRange:
    minimum: ProtocolVersion
    maximum: ProtocolVersion

    def __post_init__(self) -> None:
        if not isinstance(self.minimum, ProtocolVersion) or not isinstance(
            self.maximum, ProtocolVersion
        ):
            raise TypeError("protocol range requires typed versions")
        if self.minimum.major != self.maximum.major:
            raise ValueError("one range cannot span incompatible major versions")
        if self.maximum < self.minimum:
            raise ValueError("protocol maximum cannot precede minimum")

    def contains(self, version: ProtocolVersion) -> bool:
        return (
            isinstance(version, ProtocolVersion)
            and version.major == self.minimum.major
            and self.minimum <= version <= self.maximum
        )


def negotiate_protocol(
    left: ProtocolVersionRange, right: ProtocolVersionRange
) -> ProtocolVersion:
    """Return the highest mutually supported version or fail closed."""
    if not isinstance(left, ProtocolVersionRange) or not isinstance(
        right, ProtocolVersionRange
    ):
        raise TypeError("typed protocol ranges required")
    if left.minimum.major != right.minimum.major:
        raise RuntimeError("component SDK protocol major versions are incompatible")
    minimum = max(left.minimum, right.minimum)
    maximum = min(left.maximum, right.maximum)
    if maximum < minimum:
        raise RuntimeError("component SDK protocol ranges do not overlap")
    return maximum


class ComponentKind(str, Enum):
    PLATFORM = "platform"
    CORE = "core"
    MODULE = "module"
    INFERENCE = "inference"


@dataclass(frozen=True, slots=True)
class ComponentEndpoint:
    component_id: str
    kind: ComponentKind
    release_digest: str
    generation: int
    platform_instance_id: str
    core_identity_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.component_id, "component_id")
        if not isinstance(self.kind, ComponentKind):
            raise TypeError("kind must be ComponentKind")
        if _DIGEST.fullmatch(self.release_digest) is None:
            raise ValueError("release_digest must be SHA-256")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("generation must be positive")
        _identifier(self.platform_instance_id, "platform_instance_id")
        if self.core_identity_id is not None:
            _identifier(self.core_identity_id, "core_identity_id")
        if self.kind is ComponentKind.CORE and self.core_identity_id is None:
            raise ValueError("Core endpoint requires core_identity_id")
        if self.kind is not ComponentKind.CORE and self.core_identity_id is not None:
            raise ValueError("only a Core endpoint may carry core_identity_id")

    def to_payload(self) -> dict[str, object]:
        return {
            "component_id": self.component_id,
            "kind": self.kind.value,
            "release_digest": self.release_digest,
            "generation": self.generation,
            "platform_instance_id": self.platform_instance_id,
            "core_identity_id": self.core_identity_id,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ComponentEndpoint":
        document = _exact(payload, frozenset({
            "component_id", "kind", "release_digest", "generation",
            "platform_instance_id", "core_identity_id",
        }), "component endpoint")
        try:
            return cls(
                component_id=document["component_id"],  # type: ignore[arg-type]
                kind=ComponentKind(document["kind"]),
                release_digest=document["release_digest"],  # type: ignore[arg-type]
                generation=document["generation"],  # type: ignore[arg-type]
                platform_instance_id=document["platform_instance_id"],  # type: ignore[arg-type]
                core_identity_id=document["core_identity_id"],  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("component endpoint is invalid") from exc


@dataclass(frozen=True, slots=True)
class AuthorityProjection:
    principal_id: str
    audience_id: str
    audience_kind: str
    authority_ref: str
    scopes: tuple[str, ...]
    expires_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("principal_id", self.principal_id),
            ("audience_id", self.audience_id),
            ("authority_ref", self.authority_ref),
        ):
            _identifier(value, label)
        if self.audience_kind not in {"private", "shared", "public", "system"}:
            raise ValueError("unsupported audience_kind")
        if type(self.scopes) is not tuple or not self.scopes or len(self.scopes) > 32:
            raise ValueError("scopes must be a nonempty bounded tuple")
        normalized = tuple(_identifier(item, "scope") for item in self.scopes)
        if len(set(normalized)) != len(normalized):
            raise ValueError("scopes must be unique")
        _utc(self.expires_at, "expires_at")

    def require_current(self, *, now: datetime) -> None:
        if _utc(now, "now") >= _utc(self.expires_at, "expires_at"):
            raise PermissionError("authority projection is expired")

    def to_payload(self) -> dict[str, object]:
        return {
            "principal_id": self.principal_id,
            "audience_id": self.audience_id,
            "audience_kind": self.audience_kind,
            "authority_ref": self.authority_ref,
            "scopes": list(self.scopes),
            "expires_at": _utc(self.expires_at, "expires_at").isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "AuthorityProjection":
        document = _exact(payload, frozenset({
            "principal_id", "audience_id", "audience_kind", "authority_ref",
            "scopes", "expires_at",
        }), "authority projection")
        scopes = document["scopes"]
        if not isinstance(scopes, list):
            raise ValueError("authority scopes must be a list")
        try:
            return cls(
                principal_id=document["principal_id"],  # type: ignore[arg-type]
                audience_id=document["audience_id"],  # type: ignore[arg-type]
                audience_kind=document["audience_kind"],  # type: ignore[arg-type]
                authority_ref=document["authority_ref"],  # type: ignore[arg-type]
                scopes=tuple(scopes),
                expires_at=_time(document["expires_at"], "expires_at"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("authority projection is invalid") from exc


@dataclass(frozen=True, slots=True)
class ComponentRequestEnvelope:
    protocol: ProtocolVersion
    request_id: str
    correlation_id: str
    idempotency_key: str
    source: ComponentEndpoint
    destination: ComponentEndpoint
    authority: AuthorityProjection
    payload_type: str
    payload_digest: str
    created_at: datetime
    deadline: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, ProtocolVersion):
            raise TypeError("protocol must be ProtocolVersion")
        for label, value in (
            ("request_id", self.request_id),
            ("correlation_id", self.correlation_id),
            ("idempotency_key", self.idempotency_key),
        ):
            _identifier(value, label)
        if not isinstance(self.source, ComponentEndpoint) or not isinstance(
            self.destination, ComponentEndpoint
        ):
            raise TypeError("source and destination must be ComponentEndpoint")
        if not isinstance(self.authority, AuthorityProjection):
            raise TypeError("authority must be AuthorityProjection")
        if _PAYLOAD_TYPE.fullmatch(self.payload_type) is None:
            raise ValueError("payload_type must be a versioned schema identifier")
        if _DIGEST.fullmatch(self.payload_digest) is None:
            raise ValueError("payload_digest must be SHA-256")
        created = _utc(self.created_at, "created_at")
        deadline = _utc(self.deadline, "deadline")
        if deadline <= created:
            raise ValueError("deadline must follow created_at")
        if _utc(self.authority.expires_at, "authority.expires_at") < deadline:
            raise ValueError("request deadline exceeds projected authority")

    def require_dispatchable(
        self, *, now: datetime, expected_destination_generation: int
    ) -> None:
        moment = _utc(now, "now")
        self.authority.require_current(now=moment)
        if moment >= _utc(self.deadline, "deadline"):
            raise TimeoutError("component request deadline expired")
        if (
            type(expected_destination_generation) is not int
            or expected_destination_generation < 1
        ):
            raise ValueError("expected destination generation must be positive")
        if self.destination.generation != expected_destination_generation:
            raise PermissionError("destination generation is stale")

    def to_payload(self) -> dict[str, object]:
        return {
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "source": self.source.to_payload(),
            "destination": self.destination.to_payload(),
            "authority": self.authority.to_payload(),
            "payload_type": self.payload_type,
            "payload_digest": self.payload_digest,
            "created_at": _utc(self.created_at, "created_at").isoformat(),
            "deadline": _utc(self.deadline, "deadline").isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ComponentRequestEnvelope":
        document = _exact(payload, frozenset({
            "protocol", "request_id", "correlation_id", "idempotency_key",
            "source", "destination", "authority", "payload_type",
            "payload_digest", "created_at", "deadline",
        }), "component request")
        try:
            return cls(
                protocol=ProtocolVersion.parse(document["protocol"]),  # type: ignore[arg-type]
                request_id=document["request_id"],  # type: ignore[arg-type]
                correlation_id=document["correlation_id"],  # type: ignore[arg-type]
                idempotency_key=document["idempotency_key"],  # type: ignore[arg-type]
                source=ComponentEndpoint.from_payload(document["source"]),
                destination=ComponentEndpoint.from_payload(document["destination"]),
                authority=AuthorityProjection.from_payload(document["authority"]),
                payload_type=document["payload_type"],  # type: ignore[arg-type]
                payload_digest=document["payload_digest"],  # type: ignore[arg-type]
                created_at=_time(document["created_at"], "created_at"),
                deadline=_time(document["deadline"], "deadline"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("component request is invalid") from exc


class ComponentOutcome(str, Enum):
    DENIED = "denied"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"
    SUCCEEDED_REPORTED_UNVERIFIED = "succeeded_reported_unverified"
    SUCCEEDED_VERIFIED = "succeeded_verified"


@dataclass(frozen=True, slots=True)
class ComponentResponseEnvelope:
    protocol: ProtocolVersion
    request_id: str
    correlation_id: str
    responder: ComponentEndpoint
    outcome: ComponentOutcome
    payload_type: str | None
    payload_digest: str | None
    evidence_refs: tuple[str, ...]
    completed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, ProtocolVersion):
            raise TypeError("protocol must be ProtocolVersion")
        _identifier(self.request_id, "request_id")
        _identifier(self.correlation_id, "correlation_id")
        if not isinstance(self.responder, ComponentEndpoint):
            raise TypeError("responder must be ComponentEndpoint")
        if not isinstance(self.outcome, ComponentOutcome):
            raise TypeError("outcome must be ComponentOutcome")
        if (self.payload_type is None) != (self.payload_digest is None):
            raise ValueError("payload type and digest must be present together")
        if self.payload_type is not None:
            if _PAYLOAD_TYPE.fullmatch(self.payload_type) is None:
                raise ValueError("payload_type must be a versioned schema identifier")
            if _DIGEST.fullmatch(self.payload_digest or "") is None:
                raise ValueError("payload_digest must be SHA-256")
        if type(self.evidence_refs) is not tuple or len(self.evidence_refs) > 32:
            raise ValueError("evidence_refs must be a bounded tuple")
        for ref in self.evidence_refs:
            _identifier(ref, "evidence_ref")
        if self.outcome is ComponentOutcome.SUCCEEDED_VERIFIED and not self.evidence_refs:
            raise ValueError("verified success requires independent evidence")
        _utc(self.completed_at, "completed_at")

    def to_payload(self) -> dict[str, object]:
        return {
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "responder": self.responder.to_payload(),
            "outcome": self.outcome.value,
            "payload_type": self.payload_type,
            "payload_digest": self.payload_digest,
            "evidence_refs": list(self.evidence_refs),
            "completed_at": _utc(self.completed_at, "completed_at").isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "ComponentResponseEnvelope":
        document = _exact(payload, frozenset({
            "protocol", "request_id", "correlation_id", "responder", "outcome",
            "payload_type", "payload_digest", "evidence_refs", "completed_at",
        }), "component response")
        evidence = document["evidence_refs"]
        if not isinstance(evidence, list):
            raise ValueError("response evidence_refs must be a list")
        try:
            return cls(
                protocol=ProtocolVersion.parse(document["protocol"]),  # type: ignore[arg-type]
                request_id=document["request_id"],  # type: ignore[arg-type]
                correlation_id=document["correlation_id"],  # type: ignore[arg-type]
                responder=ComponentEndpoint.from_payload(document["responder"]),
                outcome=ComponentOutcome(document["outcome"]),
                payload_type=document["payload_type"],  # type: ignore[arg-type]
                payload_digest=document["payload_digest"],  # type: ignore[arg-type]
                evidence_refs=tuple(evidence),
                completed_at=_time(document["completed_at"], "completed_at"),
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("component response is invalid") from exc
