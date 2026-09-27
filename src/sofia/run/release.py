from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile

from sofia.dev.release import ReleaseManifest
from sofia.dev.release_store import ReleaseStateStore
from sofia.safe.release import ReleaseActivationGuard


class ReleaseManagerError(RuntimeError):
    pass


def directory_sha256(root: Path) -> str:
    """Deterministic digest of a release tree; symlinks are forbidden."""
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")
    if not root.is_dir():
        raise FileNotFoundError("release artifact directory does not exist")
    digest = sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file() or item.is_symlink()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.is_symlink():
            raise ReleaseManagerError(
                f"release artifact may not contain symlink: {path}"
            )
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


class ReleaseManager:
    """
    Stage and activate immutable Sofía releases.

    The State Plane is authoritative. active-release.json is a recoverable
    filesystem projection consumed by a launcher/service boundary.
    """

    def __init__(
        self,
        *,
        release_root: Path,
        store: ReleaseStateStore,
        guard: ReleaseActivationGuard,
    ) -> None:
        if not isinstance(release_root, Path):
            raise TypeError("release_root must be a Path")
        if not isinstance(store, ReleaseStateStore):
            raise TypeError("store must be a ReleaseStateStore")
        if not isinstance(guard, ReleaseActivationGuard):
            raise TypeError("guard must be a ReleaseActivationGuard")
        self.release_root = release_root
        self.releases_dir = release_root / "releases"
        self.pointer_path = release_root / "active-release.json"
        self.store = store
        self.guard = guard
        self.releases_dir.mkdir(parents=True, exist_ok=True)

    def candidate_path(self, release_id: str) -> Path:
        manifest = self.store.candidate(release_id)
        if manifest is None:
            raise KeyError(f"unknown release candidate: {release_id}")
        return self.releases_dir / manifest.release_id

    def stage(
        self,
        manifest: ReleaseManifest,
        source_dir: Path,
    ) -> Path:
        if not isinstance(manifest, ReleaseManifest):
            raise TypeError("manifest must be a ReleaseManifest")
        if not isinstance(source_dir, Path):
            raise TypeError("source_dir must be a Path")
        if manifest.artifact_sha256 is None:
            raise ReleaseManagerError(
                "production activation requires artifact_sha256"
            )
        observed = directory_sha256(source_dir)
        if observed != manifest.artifact_sha256:
            raise ReleaseManagerError(
                "release source tree does not match signed artifact digest"
            )

        target = self.releases_dir / manifest.release_id
        if target.exists():
            if not target.is_dir():
                raise ReleaseManagerError(
                    "release target exists but is not a directory"
                )
            if directory_sha256(target) != manifest.artifact_sha256:
                raise ReleaseManagerError(
                    "existing staged release digest does not match manifest"
                )
            self.store.save_candidate(manifest)
            return target

        with tempfile.TemporaryDirectory(
            prefix=f".{manifest.release_id}.",
            dir=self.releases_dir,
        ) as temp_root:
            staged = Path(temp_root) / "payload"
            shutil.copytree(source_dir, staged)
            if directory_sha256(staged) != manifest.artifact_sha256:
                raise ReleaseManagerError(
                    "staged release digest changed during copy"
                )
            try:
                os.replace(staged, target)
            except OSError as exc:
                raise ReleaseManagerError(
                    "unable to atomically publish staged release"
                ) from exc

        self.store.save_candidate(manifest)
        return target

    def _active_manifest(self) -> ReleaseManifest | None:
        active = self.store.active()
        if active is None:
            return None
        release_id = active.get("release_id")
        if not isinstance(release_id, str) or not release_id:
            raise ReleaseManagerError(
                "active release record has no release_id"
            )
        manifest = self.store.candidate(release_id)
        if manifest is None:
            raise ReleaseManagerError(
                "active release manifest is missing"
            )
        return manifest

    def activate(
        self,
        *,
        manifest: ReleaseManifest,
        source_dir: Path,
        signature: bytes,
        signer_key_id: str,
        now: datetime,
    ) -> Path:
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        active_manifest = self._active_manifest()
        evidence = self.guard.verify(
            manifest=manifest,
            signature=signature,
            signer_key_id=signer_key_id,
            active_manifest=active_manifest,
            verified_at=now.astimezone(timezone.utc),
        )
        target = self.stage(manifest, source_dir)
        self.store.activate(manifest, evidence)
        self.reconcile_pointer()
        return target

    def rollback_failed_release(
        self,
        *,
        failed_release_id: str,
        reason: str,
        now: datetime,
    ) -> Path:
        active = self.store.active()
        if active is None:
            raise ReleaseManagerError("no active release to roll back")
        if active.get("release_id") != failed_release_id:
            raise ReleaseManagerError(
                "rollback target is not the active release"
            )
        previous_id = active.get("previous_release_id")
        if not isinstance(previous_id, str) or not previous_id:
            raise ReleaseManagerError(
                "active release has no previous accepted release"
            )
        previous_path = self.releases_dir / previous_id
        if not previous_path.is_dir():
            raise ReleaseManagerError(
                "previous accepted release directory is missing"
            )
        previous_manifest = self.store.candidate(previous_id)
        if previous_manifest is None or previous_manifest.artifact_sha256 is None:
            raise ReleaseManagerError(
                "previous release artifact identity is missing"
            )
        if directory_sha256(previous_path) != previous_manifest.artifact_sha256:
            raise ReleaseManagerError(
                "previous release artifact failed integrity verification"
            )

        self.store.rollback_to_previous(
            failed_release_id=failed_release_id,
            at=now.astimezone(timezone.utc),
            reason=reason,
        )
        self.reconcile_pointer()
        return previous_path

    def reconcile_pointer(self) -> dict | None:
        active = self.store.active()
        if active is None:
            if self.pointer_path.exists():
                raise ReleaseManagerError(
                    "filesystem release pointer exists without authoritative state"
                )
            return None

        release_id = active.get("release_id")
        manifest_digest = active.get("manifest_sha256")
        if not isinstance(release_id, str) or not release_id:
            raise ReleaseManagerError("active release ID is invalid")
        manifest = self.store.candidate(release_id)
        if manifest is None:
            raise ReleaseManagerError("active release manifest is missing")
        if manifest.manifest_sha256 != manifest_digest:
            raise ReleaseManagerError(
                "active release manifest digest does not match control state"
            )
        target = self.releases_dir / release_id
        if not target.is_dir():
            raise ReleaseManagerError(
                "active release directory does not exist"
            )
        if (
            manifest.artifact_sha256 is None
            or directory_sha256(target) != manifest.artifact_sha256
        ):
            raise ReleaseManagerError(
                "active release artifact integrity check failed"
            )

        document = {
            "release_id": release_id,
            "manifest_sha256": manifest.manifest_sha256,
            "path": str(target.resolve()),
            "previous_release_id": active.get("previous_release_id"),
            "verified_at": active.get("verified_at"),
        }
        self.release_root.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=".active-release.",
            suffix=".json",
            dir=self.release_root,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    document,
                    handle,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.pointer_path)
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
        return document
