from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from sofia.clean.planner import CleanupCandidate, CleanupPlan, ReleaseCleanupPlanner
from sofia.clean.recovery import RecoverySnapshotManager


NOW = datetime(2026, 9, 28, 18, 0, tzinfo=timezone.utc)


def _release(root: Path, name: str, mtime: float) -> Path:
    path = root / name
    path.mkdir()
    (path / "marker.txt").write_text(name, encoding="utf-8")
    import os
    os.utime(path, (mtime, mtime))
    return path


def test_cleanup_plan_never_selects_active_or_rollback_release(tmp_path):
    root = tmp_path / "releases"
    root.mkdir()
    _release(root, "active", 40)
    _release(root, "previous", 30)
    _release(root, "recent-extra", 20)
    old = _release(root, "old", 10)

    plan = ReleaseCleanupPlanner(root).plan(
        active_release_id="active",
        previous_release_id="previous",
        retain_additional=1,
    )

    assert {item.path.name for item in plan.keep} == {
        "active",
        "previous",
        "recent-extra",
    }
    assert tuple(item.path for item in plan.delete) == (old,)
    assert plan.safe_to_apply is True


def test_cleanup_apply_requires_verified_recovery_and_refuses_protected_paths(
    tmp_path,
):
    target = tmp_path / "old"
    target.mkdir()
    candidate = CleanupCandidate(target, "test")

    with pytest.raises(PermissionError, match="verified recovery"):
        ReleaseCleanupPlanner.apply(
            CleanupPlan((), (candidate,)),
            recovery_verified=False,
        )

    protected = CleanupCandidate(target, "active", protected=True)
    with pytest.raises(PermissionError, match="protected"):
        ReleaseCleanupPlanner.apply(
            CleanupPlan((), (protected,)),
            recovery_verified=True,
        )

    assert target.exists()


def test_cleanup_apply_removes_only_planned_unprotected_directories(tmp_path):
    target = tmp_path / "old"
    target.mkdir()
    (target / "payload.txt").write_text("old", encoding="utf-8")

    removed = ReleaseCleanupPlanner.apply(
        CleanupPlan(
            keep=(),
            delete=(CleanupCandidate(target, "superseded"),),
        ),
        recovery_verified=True,
    )

    assert removed == (target,)
    assert target.exists() is False


def test_recovery_snapshot_is_verified_and_detects_tampering(tmp_path):
    source = tmp_path / "state.db"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE sample(value TEXT NOT NULL)")
        db.execute("INSERT INTO sample(value) VALUES ('safe')")

    manager = RecoverySnapshotManager(tmp_path / "recovery")
    snapshot = manager.snapshot_sqlite(
        source,
        label="state",
        now=NOW,
    )

    assert snapshot.verified is True
    assert manager.verify(snapshot) is True
    assert snapshot.snapshot.is_file()
    assert snapshot.snapshot.with_suffix(
        snapshot.snapshot.suffix + ".json"
    ).is_file()

    with snapshot.snapshot.open("ab") as fh:
        fh.write(b"tamper")

    assert manager.verify(snapshot) is False
