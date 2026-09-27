"""Deterministic construction of unsigned immutable release candidates."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sofia.release_integrity.manifest import (
    ArtifactDigest,
    CompatibilityWindow,
    ModelIdentity,
    ReleaseManifest,
)


@dataclass(frozen=True, slots=True)
class ReleaseBuildInputs:
    release_id: str
    git_revision: str
    application_version: str
    python_version: str
    dependency_lock: bytes
    state_schema: CompatibilityWindow
    fleet_protocol: CompatibilityWindow
    agent_protocol: CompatibilityWindow
    constitution_digest: str
    protected_state_schema_revision: int
    configuration_schema_revision: int
    artifacts: tuple[tuple[str, bytes], ...] = ()
    model: ModelIdentity | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.dependency_lock, bytes) or not self.dependency_lock:
            raise ValueError("dependency_lock must contain exact lock bytes")
        if not isinstance(self.artifacts, tuple):
            raise TypeError("artifacts must be a tuple")
        seen: set[str] = set()
        for artifact_id, payload in self.artifacts:
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise ValueError("artifact ID required")
            if artifact_id in seen:
                raise ValueError("artifact IDs must be unique")
            seen.add(artifact_id)
            if not isinstance(payload, bytes):
                raise TypeError("artifact payload must be bytes")


def build_unsigned_manifest(inputs: ReleaseBuildInputs) -> ReleaseManifest:
    """Build exact release identity without granting signing authority."""

    if not isinstance(inputs, ReleaseBuildInputs):
        raise TypeError("ReleaseBuildInputs required")
    artifacts = tuple(
        ArtifactDigest(
            artifact_id=artifact_id,
            digest=sha256(payload).hexdigest(),
        )
        for artifact_id, payload in inputs.artifacts
    )
    return ReleaseManifest(
        release_id=inputs.release_id,
        git_revision=inputs.git_revision,
        application_version=inputs.application_version,
        python_version=inputs.python_version,
        dependency_lock_digest=sha256(inputs.dependency_lock).hexdigest(),
        state_schema=inputs.state_schema,
        fleet_protocol=inputs.fleet_protocol,
        agent_protocol=inputs.agent_protocol,
        constitution_digest=inputs.constitution_digest,
        protected_state_schema_revision=(
            inputs.protected_state_schema_revision
        ),
        configuration_schema_revision=(
            inputs.configuration_schema_revision
        ),
        artifacts=artifacts,
        model=inputs.model,
        signature=None,
    )
