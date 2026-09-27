from __future__ import annotations

from datetime import datetime
import json

from sofia.dev.release import ReleaseManifest
from sofia.safe.release import ReleaseActivationEvidence
from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class ReleaseStateStore:
    """Durable candidate, activation-history and active-release state."""

    CANDIDATE_NAMESPACE = "release-candidate"
    HISTORY_NAMESPACE = "release-activation-history"
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


    def candidate(self, release_id: str) -> ReleaseManifest | None:
        if not isinstance(release_id, str) or not release_id.strip():
            raise ValueError("release_id must be nonempty")
        record = self._state_plane.read(
            StateKey(
                namespace=self.CANDIDATE_NAMESPACE,
                key=release_id,
            )
        )
        if record is None:
            return None
        return ReleaseManifest.from_canonical_bytes(record.value)

    def accepted(self, release_id: str) -> bool:
        if not isinstance(release_id, str) or not release_id.strip():
            raise ValueError("release_id must be nonempty")
        return self._state_plane.read(
            StateKey(
                namespace=self.HISTORY_NAMESPACE,
                key=release_id,
            )
        ) is not None

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
        history_key = StateKey(
            namespace=self.HISTORY_NAMESPACE,
            key=manifest.release_id,
        )
        history = self._state_plane.read(history_key)
        history_payload = json.dumps(
            {
                "release_id": manifest.release_id,
                "manifest_sha256": manifest.manifest_sha256,
                "signer_key_id": evidence.signer_key_id,
                "verified_at": evidence.verified_at.isoformat(),
                "previous_release_id": (
                    None if previous is None else previous["release_id"]
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if history is None:
            self._state_plane.write(
                StateRecord(
                    key=history_key,
                    state_class=StateClass.PROTECTED,
                    revision=1,
                    value=history_payload,
                    updated_at=evidence.verified_at,
                    source=f"release-acceptance:{evidence.signer_key_id}",
                ),
                expected_revision=None,
            )
        elif history.value != history_payload:
            raise RuntimeError(
                "accepted release history cannot be rewritten"
            )

        previous = self.active()
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


    def rollback_to_previous(
        self,
        *,
        failed_release_id: str,
        at: datetime,
        reason: str,
    ) -> dict:
        if not isinstance(failed_release_id, str) or not failed_release_id.strip():
            raise ValueError("failed_release_id must be nonempty")
        if not isinstance(at, datetime):
            raise TypeError("at must be a datetime")
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be timezone-aware")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        active = self.active()
        if active is None or active.get("release_id") != failed_release_id:
            raise RuntimeError(
                "automatic rollback may target only the current active release"
            )
        previous_id = active.get("previous_release_id")
        if not isinstance(previous_id, str) or not previous_id:
            raise RuntimeError("no previous accepted release is available")
        if not self.accepted(previous_id):
            raise PermissionError(
                "previous release lacks protected acceptance history"
            )
        previous = self.candidate(previous_id)
        if previous is None:
            raise RuntimeError("previous accepted release manifest is missing")

        key = StateKey(
            namespace=self.CONTROL_NAMESPACE,
            key="active",
        )
        existing = self._state_plane.read(key)
        if existing is None:
            raise RuntimeError("active release control record is missing")
        value = json.dumps(
            {
                "release_id": previous.release_id,
                "manifest_sha256": previous.manifest_sha256,
                "signer_key_id": active.get("signer_key_id"),
                "verified_at": at.isoformat(),
                "previous_release_id": failed_release_id,
                "rollback_reason": reason,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self._state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.PROTECTED,
                revision=existing.revision + 1,
                value=value,
                updated_at=at,
                source="release:auto-rollback",
            ),
            expected_revision=existing.revision,
        )
        return self.active()
