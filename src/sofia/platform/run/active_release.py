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

from sofia.platform.dev.release_store import ReleaseStateStore
from sofia.platform.run.release import directory_sha256
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.verify.component_artifacts import (
    ComponentArtifactError,
    inspect_wheel,
    wheel_matches_identity,
)


class ActiveReleaseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ActiveRelease:
    release_id: str
    manifest_sha256: str
    artifact_sha256: str
    application_version: str
    artifact_path: Path
    wheel_path: Path | None
    dependency_lock_path: Path
    component_wheels: tuple[Path, ...] = ()


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
        # A symlink/junction may redirect the authoritative release pointer
        # outside the operator-owned release root even when bytes look valid.
        if self.pointer_path.is_symlink():
            raise ActiveReleaseError("active-release pointer must not be redirected")
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

        candidate_target = self.releases_dir / release_id
        if candidate_target.is_symlink() or self.releases_dir.is_symlink():
            raise ActiveReleaseError("active release directory must not be redirected")
        target = candidate_target.resolve()
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

        component_wheels: tuple[Path, ...] = ()
        if manifest.components:
            if len(wheels) != len(manifest.components):
                raise ActiveReleaseError(
                    "active component release wheel count mismatch"
                )
            resolved: list[Path] = []
            for component in sorted(
                manifest.components,
                key=lambda component: component.component,
            ):
                matches = [
                    wheel
                    for wheel in wheels
                    if wheel_matches_identity(
                        wheel,
                        {
                            "distribution": component.distribution,
                            "version": component.version,
                            "sha256": component.sha256,
                        },
                    )
                ]
                if len(matches) != 1:
                    raise ActiveReleaseError(
                        f"active component release wheel for "
                        f"{component.distribution!r} is absent, duplicated or tampered"
                    )
                resolved.append(matches[0])
            component_wheels = tuple(resolved)
            platform_identity = next(
                (
                    component
                    for component in manifest.components
                    if component.component == "platform"
                ),
                None,
            )
            if (
                platform_identity is None
                or platform_identity.version != manifest.application_version
            ):
                raise ActiveReleaseError(
                    "component release application version is not the platform version"
                )
        else:
            if len(wheels) != 1:
                raise ActiveReleaseError(
                    "active release artifact must contain exactly one Sofía wheel"
                )

        return ActiveRelease(
            release_id=release_id,
            manifest_sha256=manifest_digest,
            artifact_sha256=manifest.artifact_sha256,
            application_version=manifest.application_version,
            artifact_path=target,
            wheel_path=wheels[0] if len(wheels) == 1 and not component_wheels else None,
            dependency_lock_path=dependency_lock,
            component_wheels=component_wheels,
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
        if environments_root is not None:
            candidate = environments_root.absolute()
            self._require_direct_path(candidate)
            self.environments_root = candidate.resolve()
        else:
            self.environments_root = self.release_root / "environments"

    @staticmethod
    def _require_direct_path(path: Path) -> None:
        try:
            assert_no_redirected_components(path, include_leaf=True)
        except PermissionError as error:
            raise ActiveReleaseError(
                "release environment contains filesystem redirection"
            ) from error

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
    def _stamp(release) -> dict[str, object]:
        stamp: dict[str, object] = {
            "release_id": release.release_id,
            "manifest_sha256": release.manifest_sha256,
            "artifact_sha256": release.artifact_sha256,
            "application_version": release.application_version,
        }
        component_wheels = getattr(release, "component_wheels", ())
        if component_wheels:
            stamp["component_wheels"] = sorted(
                wheel.name for wheel in component_wheels
            )
        return stamp

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
        self._require_direct_path(self.environments_root)
        self.environments_root.mkdir(parents=True, exist_ok=True)
        self._require_direct_path(self.environments_root)
        target = self.environments_root / release.release_id
        self._require_direct_path(target)
        # A crash during replacement can leave the prior runtime in a
        # reserved rollback path. Do not erase that evidence or auto-resume.
        if any(self.environments_root.glob(
            f".{release.release_id}.rollback-*"
        )):
            raise ActiveReleaseError(
                "unfinished release environment publication requires reconciliation"
            )
        if self._matches(target, release):
            return PreparedReleaseEnvironment(
                release,
                target,
                self._python(target),
            )

        staging = self.environments_root / (
            f".{release.release_id}.{uuid.uuid4().hex}"
        )
        self._require_direct_path(staging)
        if staging.exists():
            raise ActiveReleaseError("release staging path already exists")
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
            if release.component_wheels:
                for wheel in release.component_wheels:
                    self._run(
                        [
                            str(python_path),
                            "-m",
                            "pip",
                            "install",
                            "--disable-pip-version-check",
                            "--no-deps",
                            str(wheel),
                        ]
                    )
                self._run(
                    [str(python_path), "-m", "pip", "check"],
                    timeout=120,
                )
            else:
                if release.wheel_path is None:
                    raise ActiveReleaseError(
                        "active release has neither an integrated wheel nor components"
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
            # An installed component release contains three separate
            # distributions. Check *each* installed version against the
            # bytes actually selected by the verified release resolver.
            if release.component_wheels:
                expected_distributions: list[tuple[str, str]] = []
                for wheel in release.component_wheels:
                    name = wheel.name.split("-", 1)[0].replace("_", "-")
                    if name not in {"sofia-sdk", "sofia-platform", "sofia-core"}:
                        raise ActiveReleaseError(
                            f"unexpected component wheel distribution: {wheel.name}"
                        )
                    try:
                        metadata = inspect_wheel(wheel, name)
                    except ComponentArtifactError as error:
                        raise ActiveReleaseError(
                            "component wheel metadata failed verification"
                        ) from error
                    expected_distributions.append((name, metadata.version))
                if sorted(name for name, _ in expected_distributions) != [
                    "sofia-core", "sofia-platform", "sofia-sdk"
                ]:
                    raise ActiveReleaseError(
                        "release environment requires exactly one SDK, Platform and Core wheel"
                    )
            else:
                expected_distributions = [
                    ("sofia-ada-lyra", release.application_version)
                ]
            for distribution, expected_version in expected_distributions:
                observed_version = self._run(
                    [
                        str(python_path),
                        "-c",
                        (
                            "from importlib.metadata import version;"
                            f"print(version({distribution!r}))"
                        ),
                    ],
                    timeout=60,
                )
                if observed_version.strip() != expected_version:
                    raise ActiveReleaseError(
                        f"prepared release environment {distribution} version mismatch"
                    )
            self._stamp_path(staging).write_text(
                json.dumps(
                    self._stamp(release),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            # Keep the old release intact until the new staging environment
            # has actually been published. Do not delete the rollback copy
            # before a successful rename.
            previous: Path | None = None
            self._require_direct_path(self.environments_root)
            self._require_direct_path(staging)
            self._require_direct_path(target)
            if target.exists():
                previous = self.environments_root / (
                    f".{release.release_id}.rollback-{uuid.uuid4().hex}"
                )
                os.replace(target, previous)
            try:
                os.replace(staging, target)
            except BaseException:
                if previous is not None:
                    try:
                        os.replace(previous, target)
                    except OSError as error:
                        raise ActiveReleaseError(
                            "release environment rollback failed; "
                            "manual reconciliation required"
                        ) from error
                raise
            if previous is not None:
                try:
                    shutil.rmtree(previous)
                except OSError:
                    # A surviving rollback marker blocks later automatic
                    # replacement pending manual reconciliation.
                    pass
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return PreparedReleaseEnvironment(
            release,
            target,
            self._python(target),
        )
