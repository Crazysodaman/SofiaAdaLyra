from __future__ import annotations

from datetime import datetime
import json

from sofia.dev.release import ReleaseManifest
from sofia.safe.release import ReleaseActivationEvidence
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class ReleaseStateStore:
    """Durable candidate and active-release state through the State Plane."""

    CANDIDATE_NAMESPACE = "release-candidate"
    CONTROL_NAMESPACE = "release-control"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be a StatePlane")
        self._state_plane = state_plane

    def save_candidate(self, manifest: ReleaseManifest) -> ReleaseManifest:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        key = StateKey(
            namespace=self.CANDIDATE_NAMESPACE,
            key=manifest.release_id,
        )
        existing = self._state_plane.read(key)
        payload = manifest.canonical_bytes()
        if existing is not None:
            if existing.value != payload:
                raise RuntimeError(
                    "release_id is already bound to a different manifest"
                )
            return manifest

        self._state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.IMMUTABLE_ARTIFACT,
                revision=1,
                value=payload,
                updated_at=manifest.created_at,
                source=f"release-manifest:{manifest.manifest_sha256}",
            ),
            expected_revision=None,
        )
        return manifest

    def activate(
        self,
        manifest: ReleaseManifest,
        evidence: ReleaseActivationEvidence,
    ) -> str:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if not isinstance(evidence, ReleaseActivationEvidence):
            raise TypeError("evidence must be ReleaseActivationEvidence")
        if not evidence.accepted:
            raise PermissionError("release activation evidence is not accepted")
        if evidence.release_id != manifest.release_id:
            raise PermissionError("activation evidence names another release")
        if evidence.manifest_sha256 != manifest.manifest_sha256:
            raise PermissionError("activation evidence manifest digest mismatch")

        self.save_candidate(manifest)
        key = StateKey(
            namespace=self.CONTROL_NAMESPACE,
            key="active",
        )
        existing = self._state_plane.read(key)
        revision = 1 if existing is None else existing.revision + 1
        value = json.dumps(
            {
                "release_id": manifest.release_id,
                "manifest_sha256": manifest.manifest_sha256,
                "signer_key_id": evidence.signer_key_id,
                "verified_at": evidence.verified_at.isoformat(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        persisted = self._state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.PROTECTED,
                revision=revision,
                value=value,
                updated_at=evidence.verified_at,
                source=f"release-activation:{evidence.signer_key_id}",
            ),
            expected_revision=None if existing is None else existing.revision,
        )
        return persisted.key.key

    def active(self) -> dict | None:
        record = self._state_plane.read(
            StateKey(
                namespace=self.CONTROL_NAMESPACE,
                key="active",
            )
        )
        if record is None:
            return None
        return json.loads(record.value.decode("utf-8"))
