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


def test_recovery_snapshot_and_verification_close_database_handles(tmp_path, monkeypatch):
    import sqlite3
    import sofia.clean.recovery as recovery_module

    source = tmp_path / "source.db"
    db = sqlite3.connect(source)
    db.execute("CREATE TABLE evidence (value TEXT)")
    db.execute("INSERT INTO evidence VALUES ('retained')")
    db.commit()
    db.close()
    connections = []
    connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        connection = connect(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(recovery_module.sqlite3, "connect", tracked_connect)
    manager = recovery_module.RecoverySnapshotManager(tmp_path / "recovery")
    snapshot = manager.snapshot_sqlite(source)
    assert snapshot.verified and manager.verify(snapshot)
    assert len(connections) == 4
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    with connect(snapshot.snapshot) as reopened:
        assert reopened.execute("SELECT value FROM evidence").fetchone() == ("retained",)
    reopened.close()
