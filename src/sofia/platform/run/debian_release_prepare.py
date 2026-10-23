"""Independent privileged preparation of a signed Debian runtime release.

Run by an OS-owned deployment boundary, never by Sofía's cognitive process.
This command performs NO SQLite access, no pointer activation, no runtime
restart, and no database migration. Versioned venvs live on root-managed /opt,
not in writable canonical state.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import sys

from sofia.dev.supply_chain import verify_release_evidence
from sofia.platform.run.active_release import ActiveRelease, ReleaseEnvironmentManager
from sofia.platform.run.github_update_watch import UpdateWatchError, verified_inbox_release
from sofia.platform.run.systemd_runtime import require_debian_guest

_SHA = re.compile(r"^[0-9a-f]{40}$")


class DebianReleasePrepareError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DebianPreparedCandidate:
    revision: str
    release_id: str
    manifest_sha256: str
    python_path: Path
    activated: bool = False
    restarted: bool = False


def _root_owned_directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise DebianReleasePrepareError("release path must be a real directory")
    info = path.stat()
    if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise DebianReleasePrepareError("release inbox/environments must be root-owned and not writable by untrusted users")


def _require_root_owned_signer_key(trusted_key: Path) -> None:
    """Require a real root-owned verifier; tests may inject a synthetic gate."""
    if (trusted_key.is_symlink() or not trusted_key.is_file()
            or trusted_key.stat().st_uid != 0):
        raise PermissionError("approved root-owned release signer public key required")


def prepare_candidate(
    *,
    inbox: Path,
    trusted_key: Path,
    signer_key_id: str,
    revision: str,
    environments: Path = Path("/opt/sofia/releases"),
) -> DebianPreparedCandidate:
    require_debian_guest()
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None or geteuid() != 0:
        raise PermissionError("Debian release preparation requires the external privileged installer")
    if not isinstance(revision, str) or _SHA.fullmatch(revision) is None:
        raise ValueError("exact committed source revision required")
    _root_owned_directory(inbox)
    _root_owned_directory(environments)
    _require_root_owned_signer_key(trusted_key)

    accepted = verified_inbox_release(
        inbox=inbox, upstream_revision=revision,
        public_key=trusted_key, signer_key_id=signer_key_id,
    )
    if accepted is None:
        raise DebianReleasePrepareError("exact signed and fully verified release bundle unavailable")
    bundle = inbox / accepted.release_id
    if bundle.is_symlink() or bundle.resolve().parent != inbox.resolve():
        raise DebianReleasePrepareError("signed release directory escaped trusted inbox")
    _root_owned_directory(bundle)
    manifest = verify_release_evidence(bundle)
    if (
        manifest.release_id != accepted.release_id
        or manifest.git_revision != accepted.revision
        or manifest.manifest_sha256 != accepted.manifest_sha256
    ):
        raise DebianReleasePrepareError("release identity changed after signature verification")
    # A Windows 3.12 release/lock must never be installed into Debian 3.13.
    expected_python = ".".join(str(part) for part in sys.version_info[:2]) + "."
    if not manifest.python_version.startswith(expected_python):
        raise DebianReleasePrepareError("release Python version is incompatible with this Debian interpreter")

    root = bundle / "artifact"
    wheels = tuple(root.glob("*.whl"))
    if len(wheels) != 1:
        raise DebianReleasePrepareError("signed bundle requires exactly one wheel")
    active = ActiveRelease(
        release_id=manifest.release_id,
        manifest_sha256=manifest.manifest_sha256,
        artifact_sha256=manifest.artifact_sha256,
        application_version=manifest.application_version,
        artifact_path=root,
        wheel_path=wheels[0],
        dependency_lock_path=root / "requirements.lock",
    )
    prepared = ReleaseEnvironmentManager(
        release_root=bundle,
        environments_root=environments,
    ).ensure(active)
    _root_owned_directory(prepared.root)
    return DebianPreparedCandidate(
        revision=manifest.git_revision,
        release_id=manifest.release_id,
        manifest_sha256=manifest.manifest_sha256,
        python_path=prepared.python_path,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage exact signed Debian Sofía release without activating")
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--trusted-key", type=Path, required=True)
    parser.add_argument("--signer-key-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--environments", type=Path, default=Path("/opt/sofia/releases"))
    args = parser.parse_args(argv)
    try:
        receipt = prepare_candidate(
            inbox=args.inbox, trusted_key=args.trusted_key,
            signer_key_id=args.signer_key_id, revision=args.revision,
            environments=args.environments,
        )
        print(
            f"prepared_signed_release={receipt.release_id} "
            f"revision={receipt.revision} manifest={receipt.manifest_sha256} "
            "activated=false restarted=false"
        )
        return 0
    except (OSError, TypeError, ValueError, RuntimeError, PermissionError, UpdateWatchError) as exc:
        print(
            f"Debian release preparation refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
