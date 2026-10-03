"""Resolve and prepare the release selected by authoritative Sofía state."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import venv

from sofia.dev.release_store import ReleaseStateStore
from sofia.run.release import directory_sha256
from sofia.state.sqlite_plane import SQLiteStatePlane


class ActiveReleaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ActiveRelease:
    release_id: str
    manifest_sha256: str
    artifact_sha256: str
    application_version: str
    artifact_path: Path
    wheel_path: Path
    dependency_lock_path: Path


class ActiveReleaseResolver:
    """Bind active State Plane release state to the filesystem projection."""

    def __init__(
        self,
        *,
        state_path: Path,
        release_root: Path | None = None,
    ) -> None:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing canonical state database required")
        self.state_path = state_path.resolve()
        self.release_root = (
            release_root.resolve()
            if release_root is not None
            else (self.state_path.parent / "release-runtime").resolve()
        )
        self.releases_dir = self.release_root / "releases"
        self.pointer_path = self.release_root / "active-release.json"

    def resolve(self) -> ActiveRelease | None:
        store = ReleaseStateStore(SQLiteStatePlane(self.state_path))
        active = store.active()
        pointer_exists = self.pointer_path.is_file()

        if active is None:
            if pointer_exists:
                raise ActiveReleaseError(
                    "filesystem active-release pointer exists without authoritative state"
                )
            return None
        if not pointer_exists:
            raise ActiveReleaseError(
                "authoritative active release has no filesystem projection"
            )

        release_id = active.get("release_id")
        manifest_digest = active.get("manifest_sha256")
        if not isinstance(release_id, str) or not release_id:
            raise ActiveReleaseError("active release ID is invalid")
        if not isinstance(manifest_digest, str) or not manifest_digest:
            raise ActiveReleaseError("active manifest digest is invalid")

        manifest = store.candidate(release_id)
        if manifest is None:
            raise ActiveReleaseError("active release manifest is missing")
        if manifest.manifest_sha256 != manifest_digest:
            raise ActiveReleaseError(
                "authoritative active manifest digest mismatch"
            )
        if manifest.artifact_sha256 is None:
            raise ActiveReleaseError("active release has no artifact digest")

        try:
            pointer = json.loads(
                self.pointer_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ActiveReleaseError(
                "active-release filesystem projection is unreadable"
            ) from exc
        if not isinstance(pointer, dict):
            raise ActiveReleaseError("active-release pointer must be an object")
        if pointer.get("release_id") != release_id:
            raise ActiveReleaseError("active-release pointer names another release")
        if pointer.get("manifest_sha256") != manifest_digest:
            raise ActiveReleaseError(
                "active-release pointer manifest digest mismatch"
            )

        target = (self.releases_dir / release_id).resolve()
        if target.parent != self.releases_dir.resolve():
            raise ActiveReleaseError("active release path escaped releases directory")
        pointer_path = pointer.get("path")
        if not isinstance(pointer_path, str):
            raise ActiveReleaseError("active-release pointer path is invalid")
        if Path(pointer_path).resolve() != target:
            raise ActiveReleaseError("active-release pointer path mismatch")
        if not target.is_dir():
            raise ActiveReleaseError("active release artifact directory is missing")
        if directory_sha256(target) != manifest.artifact_sha256:
            raise ActiveReleaseError("active release artifact digest mismatch")

        wheels = tuple(target.glob("*.whl"))
        if len(wheels) != 1:
            raise ActiveReleaseError(
                "active release artifact must contain exactly one Sofía wheel"
            )
        dependency_lock = target / "requirements.lock"
        if not dependency_lock.is_file():
            raise ActiveReleaseError(
                "active release artifact dependency lock is missing"
            )
        if sha256(dependency_lock.read_bytes()).hexdigest() != (
            manifest.dependency_lock_sha256
        ):
            raise ActiveReleaseError(
                "active release dependency lock digest mismatch"
            )

        return ActiveRelease(
            release_id=release_id,
            manifest_sha256=manifest_digest,
            artifact_sha256=manifest.artifact_sha256,
            application_version=manifest.application_version,
            artifact_path=target,
            wheel_path=wheels[0],
            dependency_lock_path=dependency_lock,
        )


@dataclass(frozen=True, slots=True)
class PreparedReleaseEnvironment:
    release: ActiveRelease
    root: Path
    python_path: Path


class ReleaseEnvironmentManager:
    """Create an isolated runtime environment for one verified active release."""

    def __init__(
        self,
        *,
        release_root: Path,
        environments_root: Path | None = None,
    ) -> None:
        if not isinstance(release_root, Path):
            raise TypeError("release_root must be a Path")
        self.release_root = release_root.resolve()
        self.environments_root = (
            environments_root.resolve()
            if environments_root is not None
            else self.release_root / "environments"
        )

    @staticmethod
    def _python(root: Path) -> Path:
        return (
            root / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else root / "bin" / "python"
        )

    @staticmethod
    def _stamp_path(root: Path) -> Path:
        return root / ".sofia-release.json"

    @staticmethod
    def _stamp(release: ActiveRelease) -> dict[str, str]:
        return {
            "release_id": release.release_id,
            "manifest_sha256": release.manifest_sha256,
            "artifact_sha256": release.artifact_sha256,
            "application_version": release.application_version,
        }

    def _matches(self, root: Path, release: ActiveRelease) -> bool:
        python_path = self._python(root)
        stamp_path = self._stamp_path(root)
        if not python_path.is_file() or not stamp_path.is_file():
            return False
        try:
            stored = json.loads(stamp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return stored == self._stamp(release)

    @staticmethod
    def _run(argv: list[str], *, timeout: int = 600) -> str:
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise ActiveReleaseError(
                f"release environment command failed: {detail}"
            )
        return completed.stdout.strip()

    def ensure(
        self,
        release: ActiveRelease,
    ) -> PreparedReleaseEnvironment:
        if not isinstance(release, ActiveRelease):
            raise TypeError("release must be ActiveRelease")
        self.environments_root.mkdir(parents=True, exist_ok=True)
        target = self.environments_root / release.release_id
        if self._matches(target, release):
            return PreparedReleaseEnvironment(
                release,
                target,
                self._python(target),
            )

        staging = self.environments_root / (
            f".{release.release_id}.{uuid.uuid4().hex}"
        )
        if staging.exists():
            shutil.rmtree(staging)
        try:
            venv.EnvBuilder(
                with_pip=True,
                clear=True,
            ).create(staging)
            python_path = self._python(staging)
            if not python_path.is_file():
                raise ActiveReleaseError(
                    "release virtual environment has no Python executable"
                )
            self._run(
                [
                    str(python_path),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--require-hashes",
                    "-r",
                    str(release.dependency_lock_path),
                ]
            )
            self._run(
                [
                    str(python_path),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-deps",
                    str(release.wheel_path),
                ]
            )
            observed_version = self._run(
                [
                    str(python_path),
                    "-c",
                    (
                        "from importlib.metadata import version;"
                        "print(version('sofia-ada-lyra'))"
                    ),
                ],
                timeout=60,
            )
            if observed_version.strip() != release.application_version:
                raise ActiveReleaseError(
                    "prepared release environment application version mismatch"
                )
            self._stamp_path(staging).write_text(
                json.dumps(
                    self._stamp(release),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            if target.exists():
                shutil.rmtree(target)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return PreparedReleaseEnvironment(
            release,
            target,
            self._python(target),
        )
