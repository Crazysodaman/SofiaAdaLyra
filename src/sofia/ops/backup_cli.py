"""Operator CLI for encrypted Sofía backup, verification and restore rehearsal."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
import tempfile

from sofia.config.defaults import production_state_path
from sofia.ops.recovery import DEFAULT_RECOVERY_OBJECTIVES
from sofia.ops.backup import (
    BackupCipher,
    BackupEngine,
    BackupManifest,
    load_backup_key,
    rotate_backups,
)


def _engine(key_path: Path) -> BackupEngine:
    return BackupEngine(BackupCipher(load_backup_key(key_path)))


def _print_manifest(manifest: BackupManifest) -> None:
    print(
        f"backup_id={manifest.backup_id} "
        f"source_host={manifest.source_host_id} "
        f"failure_domain={manifest.failure_domain} "
        f"created_at={manifest.created_at.isoformat()} "
        f"files={len(manifest.entries)} "
        f"manifest_sha256={manifest.digest}"
    )


def _create(args) -> int:
    state_path = Path(args.state_path) if args.state_path else production_state_path()
    backup_dir, evidence = _engine(Path(args.key)).create(
        state_path=state_path,
        destination_root=Path(args.destination),
        source_host_id=args.source_host or socket.gethostname(),
        failure_domain=args.failure_domain,
        now=datetime.now(timezone.utc),
    )
    print(
        f"backup created: {backup_dir} "
        f"backup_id={evidence.backup_id} "
        f"sha256={evidence.content_digest}"
    )
    return 0


def _verify(args) -> int:
    manifest = _engine(Path(args.key)).verify(Path(args.backup_dir))
    _print_manifest(manifest)
    return 0


def _restore(args) -> int:
    result = _engine(Path(args.key)).restore(
        backup_dir=Path(args.backup_dir),
        target_state_path=Path(args.target_state),
        verifier=args.verifier,
        replace_existing=args.replace_existing,
        now=datetime.now(timezone.utc),
    )
    print(
        f"restore verified: backup_id={result.backup_id} "
        f"verifier={result.verifier} "
        f"verified_at={result.verified_at.isoformat()}"
    )
    return 0


def _rehearse(args) -> int:
    engine = _engine(Path(args.key))
    backup_dir = Path(args.backup_dir)
    manifest = engine.verify(backup_dir)
    with tempfile.TemporaryDirectory(prefix="sofia-restore-rehearsal-") as root:
        target = Path(root) / "sofia.db"
        result = engine.restore(
            backup_dir=backup_dir,
            target_state_path=target,
            verifier=args.verifier,
            replace_existing=False,
            now=datetime.now(timezone.utc),
        )
        if not target.is_file():
            raise RuntimeError("restore rehearsal produced no state database")
        print(
            f"restore rehearsal passed: backup_id={result.backup_id} "
            f"source_host={manifest.source_host_id} "
            f"files={len(manifest.entries)}"
        )
    return 0


def _rotate(args) -> int:
    removed = rotate_backups(
        Path(args.root),
        keep=args.keep,
    )
    print(
        f"backup rotation complete: removed={len(removed)} keep={args.keep}"
    )
    for path in removed:
        print(path)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.ops.backup_cli"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--key", required=True)
    create.add_argument("--destination", required=True)
    create.add_argument("--failure-domain", required=True)
    create.add_argument("--state-path")
    create.add_argument("--source-host")
    create.set_defaults(handler=_create)

    verify = sub.add_parser("verify")
    verify.add_argument("--key", required=True)
    verify.add_argument("--backup-dir", required=True)
    verify.set_defaults(handler=_verify)

    restore = sub.add_parser("restore")
    restore.add_argument("--key", required=True)
    restore.add_argument("--backup-dir", required=True)
    restore.add_argument("--target-state", required=True)
    restore.add_argument("--verifier", required=True)
    restore.add_argument("--replace-existing", action="store_true")
    restore.set_defaults(handler=_restore)

    rehearse = sub.add_parser("rehearse")
    rehearse.add_argument("--key", required=True)
    rehearse.add_argument("--backup-dir", required=True)
    rehearse.add_argument("--verifier", required=True)
    rehearse.set_defaults(handler=_rehearse)

    rotate = sub.add_parser("rotate")
    rotate.add_argument("--root", required=True)
    rotate.add_argument("--keep", type=int, required=True)
    rotate.set_defaults(handler=_rotate)

    sub.add_parser("objectives")

    args = parser.parse_args(argv)
    try:
        if args.command == "objectives":
            objectives = DEFAULT_RECOVERY_OBJECTIVES
            print(
                f"rpo_seconds={objectives.rpo_seconds} "
                f"rto_seconds={objectives.rto_seconds}"
            )
            return 0
        return args.handler(args)
    except Exception as exc:
        print(
            f"backup command failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
