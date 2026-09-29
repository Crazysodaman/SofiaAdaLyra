from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sofia.clean.planner import ReleaseCleanupPlanner
from sofia.clean.recovery import RecoverySnapshotManager
from sofia.config import production_state_path


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(prog="python -m sofia.clean")
    sub=parser.add_subparsers(dest="command",required=True)

    snapshot=sub.add_parser("snapshot")
    snapshot.add_argument("--state-path")
    snapshot.add_argument("--recovery-root",required=True)
    snapshot.add_argument("--label",default="state")

    plan=sub.add_parser("plan")
    plan.add_argument("--releases-root",required=True)
    plan.add_argument("--active-release-id")
    plan.add_argument("--previous-release-id")
    plan.add_argument("--retain-additional",type=int,default=2)

    apply=sub.add_parser("apply")
    apply.add_argument("--releases-root",required=True)
    apply.add_argument("--active-release-id")
    apply.add_argument("--previous-release-id")
    apply.add_argument("--retain-additional",type=int,default=2)
    apply.add_argument("--recovery-snapshot",required=True)
    apply.add_argument("--confirm",action="store_true")

    args=parser.parse_args(argv)
    try:
        if args.command=="snapshot":
            source=(
                Path(args.state_path)
                if args.state_path
                else production_state_path()
            )
            result=RecoverySnapshotManager(Path(args.recovery_root)).snapshot_sqlite(
                source,
                label=args.label,
            )
            print(
                f"snapshot={result.snapshot} sha256={result.sha256} "
                f"bytes={result.bytes} verified={result.verified}"
            )
            return 0

        planner=ReleaseCleanupPlanner(Path(args.releases_root))
        cleanup_plan=planner.plan(
            active_release_id=args.active_release_id,
            previous_release_id=args.previous_release_id,
            retain_additional=args.retain_additional,
        )
        if args.command=="plan":
            for item in cleanup_plan.keep:
                print(f"KEEP {item.path} reason={item.reason} protected={item.protected}")
            for item in cleanup_plan.delete:
                print(f"DELETE {item.path} reason={item.reason}")
            return 0

        if args.confirm is not True:
            raise PermissionError("cleanup apply requires explicit --confirm")
        snapshot_path=Path(args.recovery_snapshot)
        if not snapshot_path.is_file():
            raise FileNotFoundError("recovery snapshot does not exist")
        manager=RecoverySnapshotManager(snapshot_path.parent)
        from sofia.clean.recovery import RecoverySnapshot
        from datetime import datetime
        manifest=snapshot_path.with_suffix(snapshot_path.suffix+".json")
        if not manifest.is_file():
            raise RuntimeError("recovery snapshot manifest is missing")
        import json
        raw=json.loads(manifest.read_text(encoding="utf-8"))
        recovery=RecoverySnapshot(
            source=Path(raw["source"]),
            snapshot=Path(raw["snapshot"]),
            sha256=raw["sha256"],
            bytes=int(raw["bytes"]),
            created_at=datetime.fromisoformat(raw["created_at"]),
            sqlite_integrity=tuple(raw["sqlite_integrity"]),
        )
        if recovery.snapshot.resolve()!=snapshot_path.resolve():
            raise RuntimeError("recovery manifest does not describe supplied snapshot")
        verified=manager.verify(recovery)
        removed=planner.apply(
            cleanup_plan,
            recovery_verified=verified,
        )
        for path in removed:
            print(f"REMOVED {path}")
        return 0
    except (OSError,PermissionError,RuntimeError,TypeError,ValueError) as exc:
        print(
            f"CLEAN refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__=="__main__":
    raise SystemExit(main())
