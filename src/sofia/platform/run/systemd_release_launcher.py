"""Stable, read-only release interpreter selector for the Debian systemd service.

The updater is OUTSIDE Sofía's running process. A privileged operator-controlled
installer prepares root-owned versioned environments. This launcher verifies the
canonical active release before exec() and NEVER creates, updates, rolls back,
or activates one. The child inherits the same PID/systemd NOTIFY_SOCKET.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import sys

from sofia.platform.run.active_release import ActiveReleaseResolver, ReleaseEnvironmentManager
from sofia.platform.run.systemd_runtime import require_debian_guest
from sofia.platform.state.canonical_sqlite import require_existing_sqlite

DEFAULT_RELEASE_ENVIRONMENTS = Path("/opt/sofia/releases")
_MAX_STAMP = 8192


class DebianReleaseLauncherError(RuntimeError):
    pass


def _privileged_read_only_dir(path: Path) -> None:
    """Require root-owned, non-group-writable release installation tree."""
    if path.is_symlink() or not path.is_dir():
        raise DebianReleaseLauncherError("release environment directory is unavailable")
    information = path.stat()
    if information.st_uid != 0 or information.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise DebianReleaseLauncherError("release environment must be root-managed")


def interpreter_for_active_release(
    *,
    state_path: Path,
    release_environments: Path = DEFAULT_RELEASE_ENVIRONMENTS,
    bootstrap_python: Path | None = None,
) -> Path:
    """Read-only selection; no second SQLite writer, venv installer or child."""
    if bootstrap_python is None:
        bootstrap_python = Path(sys.executable)
    if not isinstance(state_path, Path) or not isinstance(release_environments, Path):
        raise TypeError("release launcher requires approved Path arguments")
    require_existing_sqlite(state_path)
    active = ActiveReleaseResolver(state_path=state_path).resolve()
    if active is None:
        # Initial deployment with no activated signed release keeps the
        # operator-installed bootstrap. Never invent a release from Git HEAD.
        return bootstrap_python

    _privileged_read_only_dir(release_environments)
    target = release_environments / active.release_id
    if target.is_symlink() or target.resolve().parent != release_environments.resolve():
        raise DebianReleaseLauncherError("active release escaped approved environment root")
    _privileged_read_only_dir(target)
    stamp = target / ".sofia-release.json"
    if stamp.is_symlink() or not stamp.is_file() or stamp.stat().st_size > _MAX_STAMP:
        raise DebianReleaseLauncherError("active release has no valid prepared stamp")
    try:
        recorded = json.loads(stamp.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise DebianReleaseLauncherError("prepared release stamp is invalid") from exc
    expected = ReleaseEnvironmentManager._stamp(active)
    if recorded != expected:
        raise DebianReleaseLauncherError("prepared release does not match canonical active manifest")
    python_path = target / "bin" / "python"
    if not python_path.is_file():
        raise DebianReleaseLauncherError("prepared release interpreter is missing")
    # Python venv bin/python is normally a symlink to the installed OS Python.
    # Only the environment TREE must remain root-controlled; the interpreter
    # symlink must resolve to an absolute regular executable on this guest.
    resolved = python_path.resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise DebianReleaseLauncherError("prepared interpreter is not executable")
    return python_path


def main() -> int:
    try:
        require_debian_guest()
        if (
            os.environ.get("SOFIA_RUNTIME_MODE") != "production"
            or os.environ.get("SOFIA_IDENTITY_BOOTSTRAP_MODE") != "require_existing"
            or not os.environ.get("SOFIA_STATE_HOME_POINTER", "").strip()
            or not os.environ.get("NOTIFY_SOCKET", "").strip()
        ):
            raise PermissionError("release launcher requires approved canonical systemd runtime")
        from sofia.platform.config.defaults import production_state_path
        interpreter = interpreter_for_active_release(state_path=production_state_path())
        os.execve(
            str(interpreter),
            [str(interpreter), "-m", "sofia.platform.run.systemd_runtime"],
            dict(os.environ),
        )
    except (OSError, ValueError, TypeError, RuntimeError, PermissionError) as exc:
        print(
            "canonical Debian release launcher refused: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
