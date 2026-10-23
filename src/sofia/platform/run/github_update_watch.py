"""Independent, nonactivating GitHub update discovery for the Debian host.

GitHub main is a discovery signal, NOT deployment authority. This service
never executes pulled code, replaces an interpreter, touches sofia.db, or
restarts a process. Only exact signed, evidence-verified immutable bundles can
be recommended for the separately authorized release activation broker.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Callable

from sofia.platform.dev.supply_chain import verify_release_evidence
from sofia.platform.safe.release_ed25519 import Ed25519ReleaseSignatureVerifier


REPOSITORY = "https://github.com/Crazysodaman/SofiaAdaLyra.git"
BRANCH_REF = "refs/heads/main"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_MAX_CANDIDATES = 32
_MAX_OUTPUT = 4096


class UpdateWatchError(RuntimeError):
    """The source, local candidate or observation is not trustworthy."""


@dataclass(frozen=True, slots=True)
class VerifiedUpdate:
    revision: str
    release_id: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class UpdateObservation:
    upstream_revision: str
    installed_revision: str | None
    status: str
    verified_release: VerifiedUpdate | None
    observed_at: datetime

    def as_json(self) -> dict[str, object]:
        return {
            "schema": 1,
            "repository": "Crazysodaman/SofiaAdaLyra",
            "ref": BRANCH_REF,
            "upstream_revision": self.upstream_revision,
            "installed_revision": self.installed_revision,
            "status": self.status,
            "verified_release": (
                None if self.verified_release is None else {
                    "revision": self.verified_release.revision,
                    "release_id": self.verified_release.release_id,
                    "manifest_sha256": self.verified_release.manifest_sha256,
                }
            ),
            "observed_at": self.observed_at.astimezone(timezone.utc).isoformat(),
            "activated": False,
            "runtime_restarted": False,
        }


def git_main_revision(
    *,
    runner: Callable[..., object] = subprocess.run,
) -> str:
    """Bounded, explicit HTTPS remote inspection, never a fetch or pull."""
    command = [
        "git", "-c", "credential.helper=", "ls-remote",
        "--exit-code", REPOSITORY, BRANCH_REF,
    ]
    environment = dict(os.environ)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["GIT_ASKPASS"] = ""
    try:
        result = runner(
            command, capture_output=True, text=True, check=False,
            timeout=30, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateWatchError("GitHub revision lookup failed") from exc
    if result.returncode != 0:
        raise UpdateWatchError("GitHub revision lookup failed")
    output = result.stdout
    if not isinstance(output, str) or len(output) > _MAX_OUTPUT:
        raise UpdateWatchError("GitHub revision response exceeds bounds")
    rows = output.splitlines()
    if len(rows) != 1:
        raise UpdateWatchError("GitHub did not return exactly one main ref")
    pieces = rows[0].split("\t")
    if len(pieces) != 2 or pieces[1] != BRANCH_REF or _SHA.fullmatch(pieces[0]) is None:
        raise UpdateWatchError("GitHub returned an invalid exact main ref")
    return pieces[0]


def installed_revision_from_file(path: Path | None) -> str | None:
    """Separate deployment receipt; do not inspect or create canonical SQLite."""
    if path is None:
        return None
    if path.is_symlink():
        raise UpdateWatchError("installed revision path must not be a symlink")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 128:
        raise UpdateWatchError("installed revision receipt is invalid")
    value = path.read_text(encoding="ascii").strip()
    if _SHA.fullmatch(value) is None:
        raise UpdateWatchError("installed revision receipt has invalid SHA")
    return value


def verified_inbox_release(
    *,
    inbox: Path,
    upstream_revision: str,
    public_key: Path | None,
    signer_key_id: str | None,
) -> VerifiedUpdate | None:
    """Exact signed, locally staged release matching current public main HEAD.

    A missing key means discover-only mode, never unsigned installation.
    An untrusted or malformed bundle never becomes deployable.
    """
    if (public_key is None) != (signer_key_id is None):
        raise UpdateWatchError("release public key and signer key ID are both required")
    if public_key is None:
        return None
    if not public_key.is_file() or public_key.is_symlink():
        raise UpdateWatchError("trusted release public key is unavailable")
    verifier = Ed25519ReleaseSignatureVerifier({signer_key_id: public_key})
    if inbox.is_symlink():
        raise UpdateWatchError("release inbox must not be a symlink")
    if not inbox.exists():
        return None
    if not inbox.is_dir():
        raise UpdateWatchError("release inbox is not a directory")
    entries = list(inbox.iterdir())
    if len(entries) > _MAX_CANDIDATES:
        raise UpdateWatchError("release inbox exceeds candidate bound")
    accepted: list[VerifiedUpdate] = []
    for item in entries:
        if item.is_symlink() or not item.is_dir():
            continue
        if item.resolve().parent != inbox.resolve():
            continue
        try:
            manifest = verify_release_evidence(item)
            if manifest.git_revision != upstream_revision:
                continue
            signer = item / "signer-key-id.txt"
            signature = item / "release-signature.bin"
            if signer.is_symlink() or signature.is_symlink():
                continue
            if not signer.is_file() or not signature.is_file():
                continue
            if signer.stat().st_size > 128 or signature.stat().st_size > 2048:
                continue
            key_id = signer.read_text(encoding="utf-8").strip()
            if key_id != signer_key_id:
                continue
            if not verifier.verify(
                manifest=manifest,
                signature=signature.read_bytes(),
                signer_key_id=signer_key_id,
            ):
                continue
            accepted.append(VerifiedUpdate(
                revision=manifest.git_revision,
                release_id=manifest.release_id,
                manifest_sha256=manifest.manifest_sha256,
            ))
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            # A bad inbox candidate is never an install instruction.
            continue
    if len(accepted) > 1:
        raise UpdateWatchError("multiple signed candidates for current main; review required")
    return accepted[0] if accepted else None


def inspect_updates(
    *,
    installed_revision: str | None,
    inbox: Path,
    public_key: Path | None = None,
    signer_key_id: str | None = None,
    head_reader: Callable[[], str] = git_main_revision,
    now: datetime | None = None,
) -> UpdateObservation:
    if installed_revision is not None and _SHA.fullmatch(installed_revision) is None:
        raise UpdateWatchError("installed revision must be an exact SHA")
    revision = head_reader()
    if not isinstance(revision, str) or _SHA.fullmatch(revision) is None:
        raise UpdateWatchError("upstream revision is not an exact SHA")
    checked_at = now or datetime.now(timezone.utc)
    if checked_at.tzinfo is None:
        raise ValueError("observation time must be timezone aware")
    if installed_revision == revision:
        return UpdateObservation(revision, installed_revision, "up_to_date", None, checked_at)
    candidate = verified_inbox_release(
        inbox=inbox, upstream_revision=revision,
        public_key=public_key, signer_key_id=signer_key_id,
    )
    return UpdateObservation(
        revision, installed_revision,
        "signed_release_available" if candidate is not None else "awaiting_signed_release",
        candidate, checked_at,
    )


def publish_observation(observation: UpdateObservation, *, path: Path) -> None:
    """Atomic outside-canonical-DB observation; no exec, restart or pointer write."""
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise UpdateWatchError("observation destination must be an existing real directory")
    data = (json.dumps(observation.as_json(), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor, name = tempfile.mkstemp(prefix=".update-watch-", dir=path.parent)
    temporary = Path(name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        else:
            # The runtime watcher is Debian-only; keep source-level tests
            # importable on Windows where fchmod may not be provided.
            os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nonactivating Sofía main revision watcher")
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--installed-revision-file", type=Path, required=True)
    parser.add_argument("--inbox", type=Path, required=True)
    parser.add_argument("--trusted-release-key", type=Path)
    parser.add_argument("--signer-key-id")
    args = parser.parse_args(argv)
    try:
        installed = installed_revision_from_file(args.installed_revision_file)
        observation = inspect_updates(
            installed_revision=installed, inbox=args.inbox,
            public_key=args.trusted_release_key, signer_key_id=args.signer_key_id,
        )
        publish_observation(observation, path=args.status_file)
        print(json.dumps(observation.as_json(), sort_keys=True))
        return 0
    except (UpdateWatchError, OSError, ValueError, TypeError) as exc:
        print("Sofía update watch refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
