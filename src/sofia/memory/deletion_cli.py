"""Operator-only candidate erasure maintenance, independent of model/tool calls.

The operator must quiesce the canonical runtime before invoking this command.
This CLI never alters conversation originals or arbitrary private files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from uuid import UUID

from sofia.memory.deletion_ledger import MemoryDeletionLedger
from sofia.ops.backup import BackupCipher, load_backup_key


def _ledger(args) -> MemoryDeletionLedger:
    return MemoryDeletionLedger(
        Path(args.erasure_journal).absolute(),
        BackupCipher(load_backup_key(Path(args.key))),
    )


def _init(args) -> int:
    if args.approve_external_journal is not True:
        raise PermissionError("explicit external journal provisioning approval required")
    path = Path(args.erasure_journal).absolute()
    if path.parent == Path(args.state_path).absolute().parent:
        raise ValueError("deletion journal may not live alongside the backed-up DB")
    journal = _ledger(args)
    journal.initialize()
    print("external authenticated deletion journal initialized")
    return 0


def _forget(args) -> int:
    target = Path(args.state_path).absolute()
    if not target.is_file() or target.is_symlink():
        raise FileNotFoundError("existing stopped canonical database required")
    candidate = UUID(args.candidate_id)
    if args.confirm_candidate_id != str(candidate):
        raise PermissionError("explicit typed UUID confirmation required")
    if not args.approval_ref.strip():
        raise PermissionError("operator approval reference required")
    journal = _ledger(args)
    journal.entries()  # missing external state is an error, never a fresh journal
    # Verify live original audience before the durable deletion instruction
    # is appended. Never use model-provided IDs as an authority.
    with sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True) as db:
        scoped = db.execute(
            "SELECT principal_id,audience_id FROM memory_candidate WHERE candidate_id=?",
            (str(candidate),),
        ).fetchone()
    if scoped is not None and scoped != (args.principal_id, args.audience_id):
        raise PermissionError("requested candidate belongs to another private scope")
    if scoped is None:
        if not any(
            entry["candidate_id"] == str(candidate)
            and entry["principal_id"] == args.principal_id
            and entry["audience_id"] == args.audience_id
            for entry in journal.entries()
        ):
            raise LookupError("candidate not found in original state or signed erasure history")
    journal.request(
        candidate_id=candidate, principal_id=args.principal_id,
        audience_id=args.audience_id, authority_ref=args.approval_ref,
        at=datetime.now(timezone.utc),
        approve=lambda uid, principal, audience, approval: (
            uid == args.confirm_candidate_id
            and principal == args.principal_id
            and audience == args.audience_id
            and approval == args.approval_ref
        ),
    )
    removed = journal.apply_to_sqlite(target)
    print(
        f"memory candidate erasure journal committed; live rows removed={removed}; "
        "existing encrypted backups remain on retention schedule"
    )
    return 0


def _replay(args) -> int:
    if args.approve_replay is not True:
        raise PermissionError("operator must approve offline erasure replay")
    count = _ledger(args).apply_to_sqlite(Path(args.state_path).absolute())
    print(f"authenticated erasure replay completed: candidate rows removed={count}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.memory.deletion_cli")
    parser.add_argument("--key", required=True,
                        help="operator-held backup authentication key")
    parser.add_argument("--erasure-journal", required=True,
                        help="absolute protected path outside ALL state backups")
    parser.add_argument("--state-path", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    initial = sub.add_parser("init-journal")
    initial.add_argument("--approve-external-journal", action="store_true")
    initial.set_defaults(action=_init)
    forget = sub.add_parser("forget-candidate")
    forget.add_argument("--candidate-id", required=True)
    forget.add_argument("--confirm-candidate-id", required=True)
    forget.add_argument("--principal-id", required=True)
    forget.add_argument("--audience-id", required=True)
    forget.add_argument("--approval-ref", required=True)
    forget.set_defaults(action=_forget)
    replay = sub.add_parser("replay")
    replay.add_argument("--approve-replay", action="store_true")
    replay.set_defaults(action=_replay)
    args = parser.parse_args(argv)
    try:
        return args.action(args)
    except Exception as exc:
        print(
            f"memory erasure failed closed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
