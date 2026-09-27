"""Canonical immutable identity for one Sofía release candidate."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+\-]{0,191}$")


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    artifact_id: str
    digest: str

    def __post_init__(self) -> None:
        _identifier(self.artifact_id, "artifact_id")
        _digest(self.digest, "artifact digest")


@dataclass(frozen=True, slots=True)
class CompatibilityWindow:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if type(self.minimum) is not int or self.minimum < 0:
            raise ValueError("minimum compatibility revision must be >= 0")
        if type(self.maximum) is not int or self.maximum < self.minimum:
            raise ValueError(
                "maximum compatibility revision must be >= minimum"
            )

    def accepts(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.minimum <= revision <= self.maximum
        )


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    provider: str
    model: str
    digest: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.provider, "provider")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be non-empty")
        if self.digest is not None:
            _digest(self.digest, "model digest")


@dataclass(frozen=True, slots=True)
class ReleaseSignature:
    key_id: str
    algorithm: str
    signature: str

    def __post_init__(self) -> None:
        _identifier(self.key_id, "key_id")
        _identifier(self.algorithm, "algorithm")
        if not isinstance(self.signature, str) or not self.signature.strip():
            raise ValueError("signature must be non-empty")


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    release_id: str
    git_revision: str
    application_version: str
    python_version: str
    dependency_lock_digest: str
    state_schema: CompatibilityWindow
    fleet_protocol: CompatibilityWindow
    agent_protocol: CompatibilityWindow
    constitution_digest: str
    protected_state_schema_revision: int
    configuration_schema_revision: int
    artifacts: tuple[ArtifactDigest, ...] = ()
    model: ModelIdentity | None = None
    signature: ReleaseSignature | None = None

    def __post_init__(self) -> None:
        _identifier(self.release_id, "release_id")
        if (
            not isinstance(self.git_revision, str)
            or _GIT_REVISION.fullmatch(self.git_revision) is None
        ):
            raise ValueError("git_revision must be a full lowercase Git SHA")
        for label, value in (
            ("application_version", self.application_version),
            ("python_version", self.python_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be non-empty")
        _digest(self.dependency_lock_digest, "dependency_lock_digest")
        _digest(self.constitution_digest, "constitution_digest")
        if not isinstance(self.state_schema, CompatibilityWindow):
            raise TypeError("state_schema must be a CompatibilityWindow")
        if not isinstance(self.fleet_protocol, CompatibilityWindow):
            raise TypeError("fleet_protocol must be a CompatibilityWindow")
        if not isinstance(self.agent_protocol, CompatibilityWindow):
            raise TypeError("agent_protocol must be a CompatibilityWindow")
        for label, value in (
            (
                "protected_state_schema_revision",
                self.protected_state_schema_revision,
            ),
            (
                "configuration_schema_revision",
                self.configuration_schema_revision,
            ),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be >= 0")
        if not isinstance(self.artifacts, tuple):
            raise TypeError("artifacts must be a tuple")
        for artifact in self.artifacts:
            if not isinstance(artifact, ArtifactDigest):
                raise TypeError("artifacts must contain ArtifactDigest values")
        ids = tuple(item.artifact_id for item in self.artifacts)
        if len(set(ids)) != len(ids):
            raise ValueError("artifact IDs must be unique")
        if self.model is not None and not isinstance(
            self.model,
            ModelIdentity,
        ):
            raise TypeError("model must be a ModelIdentity or None")
        if self.signature is not None and not isinstance(
            self.signature,
            ReleaseSignature,
        ):
            raise TypeError("signature must be a ReleaseSignature or None")

    def canonical_document(self, *, include_signature: bool = False) -> dict:
        document = {
            "release_id": self.release_id,
            "git_revision": self.git_revision,
            "application_version": self.application_version,
            "python_version": self.python_version,
            "dependency_lock_digest": self.dependency_lock_digest,
            "state_schema": {
                "minimum": self.state_schema.minimum,
                "maximum": self.state_schema.maximum,
            },
            "fleet_protocol": {
                "minimum": self.fleet_protocol.minimum,
                "maximum": self.fleet_protocol.maximum,
            },
            "agent_protocol": {
                "minimum": self.agent_protocol.minimum,
                "maximum": self.agent_protocol.maximum,
            },
            "constitution_digest": self.constitution_digest,
            "protected_state_schema_revision": (
                self.protected_state_schema_revision
            ),
            "configuration_schema_revision": (
                self.configuration_schema_revision
            ),
            "artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "digest": artifact.digest,
                }
                for artifact in sorted(
                    self.artifacts,
                    key=lambda item: item.artifact_id,
                )
            ],
            "model": (
                None
                if self.model is None
                else {
                    "provider": self.model.provider,
                    "model": self.model.model,
                    "digest": self.model.digest,
                }
            ),
        }
        if include_signature:
            document["signature"] = (
                None
                if self.signature is None
                else {
                    "key_id": self.signature.key_id,
                    "algorithm": self.signature.algorithm,
                    "signature": self.signature.signature,
                }
            )
        return document

    def signing_payload(self) -> bytes:
        return json.dumps(
            self.canonical_document(include_signature=False),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @property
    def manifest_digest(self) -> str:
        return sha256(self.signing_payload()).hexdigest()
