"""Bounded, read-only filesystem workload measurements for CA-6109.

Never opens or writes an application database, creates directories, reads
private file bytes, or treats absent optional sensors as measurements.
Measurements from an operator-selected host are not a fabricated CI host
performance acceptance receipt. Disk bytes are logical file sizes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import os
import stat

from sofia.ops.capacity import (
    CapacityAssessment, CapacityError, DEFAULT_BUDGETS, Reading, assess_capacity,
)
from sofia.state.canonical_sqlite import require_existing_sqlite

_MAX_ENTRIES = 100_000
_MAX_DEPTH = 16
_ROOT_FIELDS = (
    ("archive_dir", "archive_bytes"),
    ("backup_dir", "backup_bytes"),
    ("media_dir", "media_asset_bytes"),
)


def _no_redirect(path: Path) -> Path:
    root = path.absolute()
    current = root
    while True:
        if current.is_symlink():
            raise CapacityError("redirected measurement path is not allowed")
        if current.parent == current:
            break
        current = current.parent
    return root


def _tree_size(root: Path, *, max_entries: int, max_depth: int) -> int:
    if not root.is_dir():
        raise CapacityError("measurement root must be an existing directory")
    count = 0
    total = 0
    pending: list[tuple[Path, int]] = [(root, 0)]
    while pending:
        current, depth = pending.pop()
        with os.scandir(current) as scan:
            for entry in scan:
                count += 1
                if count > max_entries:
                    raise CapacityError("measurement entry limit exceeded")
                if entry.is_symlink():
                    raise CapacityError("symlink encountered in measurement tree")
                if entry.is_dir(follow_symlinks=False):
                    if depth >= max_depth:
                        raise CapacityError("measurement nesting limit exceeded")
                    pending.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                else:
                    raise CapacityError("unexpected special file in measurement tree")
    return total


def measure_storage(
    canonical_db: Path | str,
    *,
    archive_dir: Path | str | None = None,
    backup_dir: Path | str | None = None,
    media_dir: Path | str | None = None,
    max_entries: int = _MAX_ENTRIES,
    max_depth: int = _MAX_DEPTH,
) -> tuple[Reading, ...]:
    """Return only observed usage; no missing metric becomes a fake zero."""
    if type(max_entries) is not int or not 1 <= max_entries <= _MAX_ENTRIES:
        raise CapacityError("max_entries outside allowed range")
    if type(max_depth) is not int or not 0 <= max_depth <= _MAX_DEPTH:
        raise CapacityError("max_depth outside allowed range")
    db_path, _ = require_existing_sqlite(_no_redirect(Path(canonical_db)))
    total_db = db_path.stat().st_size
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = _no_redirect(Path(str(db_path) + suffix))
        if sidecar.exists():
            mode = sidecar.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode):
                raise CapacityError("nonregular SQLite sidecar cannot be measured")
            total_db += sidecar.stat().st_size
    collected = [Reading("canonical_db_bytes", total_db)]
    selected = {
        "archive_dir": archive_dir,
        "backup_dir": backup_dir,
        "media_dir": media_dir,
    }
    chosen: list[Path] = []
    for name, resource in _ROOT_FIELDS:
        value = selected[name]
        if value is None:
            continue
        root = _no_redirect(Path(value))
        if any(root == earlier or root in earlier.parents or
               earlier in root.parents for earlier in chosen):
            raise CapacityError("overlapping measurement roots would double-count")
        chosen.append(root)
        collected.append(Reading(resource, _tree_size(
            root, max_entries=max_entries, max_depth=max_depth,
        )))
    return tuple(collected)


def report_storage(readings: tuple[Reading, ...]) -> dict:
    """Conservative report: absent CPU/SSD rate/latency remains explicitly unknown."""
    assessment: CapacityAssessment = assess_capacity(DEFAULT_BUDGETS, readings)
    return {
        "schema": "sofia.v18-capacity-host-snapshot-v1",
        "scope": "operator-selected machine; filesystem metadata only",
        "acceptance_verified": False,
        "overall": assessment.overall.value,
        "readings": {item.resource: item.used for item in readings},
        "missing_resources": [
            item.resource for item in assessment.verdicts if item.used is None
        ],
        "verdicts": [
            {
                "resource": item.resource,
                "used": item.used,
                "level": item.level.value,
                "trigger": item.trigger,
            }
            for item in assessment.verdicts
        ],
        "alerts": list(assessment.alerts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-db", required=True, type=Path)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--media-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        # Filesystem metadata only, with no database writer or host mutation.
        report = report_storage(measure_storage(
            args.canonical_db, archive_dir=args.archive_dir,
            backup_dir=args.backup_dir, media_dir=args.media_dir,
        ))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"capacity_overall={report['overall']} "
              f"unmeasured={len(report['missing_resources'])}")
        return 0
    except (OSError, ValueError, PermissionError) as exc:
        parser.exit(2, "capacity probe rejected: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
