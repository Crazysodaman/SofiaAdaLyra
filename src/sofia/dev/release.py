from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def _digest(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    """Immutable identity of one deployable Sofía release candidate."""

    release_id: str
    git_revision: str
    application_version: str
    python_version: str
    dependency_lock_sha256: str
    sbom_sha256: str
    provenance_sha256: str
    state_schema_min: int
    state_schema_max: int
    fleet_protocol_version: str
    fleet_agent_version: str
    constitution_sha256: str
    configuration_schema_version: int
    created_at: datetime
    model_id: str | None = None
    model_sha256: str | None = None
    asset_sha256: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "release_id",
            "application_version",
            "python_version",
            "fleet_protocol_version",
            "fleet_agent_version",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a nonempty string")
        if not isinstance(self.git_revision, str) or _GIT_SHA.fullmatch(
            self.git_revision
        ) is None:
            raise ValueError("git_revision must be a lowercase 40-character SHA")
        _digest(self.dependency_lock_sha256, "dependency_lock_sha256")
        _digest(self.sbom_sha256, "sbom_sha256")
        _digest(self.provenance_sha256, "provenance_sha256")
        _digest(self.constitution_sha256, "constitution_sha256")
        if type(self.state_schema_min) is not int or self.state_schema_min < 1:
            raise ValueError("state_schema_min must be a positive integer")
        if type(self.state_schema_max) is not int or self.state_schema_max < self.state_schema_min:
            raise ValueError("state_schema_max must be >= state_schema_min")
        if (
            type(self.configuration_schema_version) is not int
            or self.configuration_schema_version < 1
        ):
            raise ValueError(
                "configuration_schema_version must be a positive integer"
            )
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.model_id is not None and (
            not isinstance(self.model_id, str) or not self.model_id.strip()
        ):
            raise ValueError("model_id must be None or a nonempty string")
        if self.model_sha256 is not None:
            _digest(self.model_sha256, "model_sha256")
            if self.model_id is None:
                raise ValueError("model_sha256 requires model_id")
        if not isinstance(self.asset_sha256, tuple):
            raise TypeError("asset_sha256 must be a tuple")
        names: set[str] = set()
        for name, digest in self.asset_sha256:
            if not isinstance(name, str) or not name.strip():
                raise ValueError("asset names must be nonempty strings")
            if name in names:
                raise ValueError("asset names must be unique")
            names.add(name)
            _digest(digest, f"asset {name}")

    def canonical_bytes(self) -> bytes:
        payload = {
            "release_id": self.release_id,
            "git_revision": self.git_revision,
            "application_version": self.application_version,
            "python_version": self.python_version,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "sbom_sha256": self.sbom_sha256,
            "provenance_sha256": self.provenance_sha256,
            "state_schema_min": self.state_schema_min,
            "state_schema_max": self.state_schema_max,
            "fleet_protocol_version": self.fleet_protocol_version,
            "fleet_agent_version": self.fleet_agent_version,
            "constitution_sha256": self.constitution_sha256,
            "configuration_schema_version": self.configuration_schema_version,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "asset_sha256": sorted(self.asset_sha256),
        }
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def supports_state_schema(self, revision: int) -> bool:
        return (
            type(revision) is int
            and self.state_schema_min <= revision <= self.state_schema_max
        )
