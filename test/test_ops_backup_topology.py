from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3

import pytest

from sofia.ops.backup import BackupCipher, BackupEngine
from sofia.ops.backup_topology import (
    BackupTarget,
    BackupTopologyError,
    BackupTopologyJournal,
    BackupTopologyPolicy,
    MultiHostBackupCoordinator,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


NOW = datetime(2026, 10, 4, 18, 30, tzinfo=timezone.utc)


def make_state(tmp_path: Path) -> Path:
    path = tmp_path / "live" / "sofia.db"
    path.parent.mkdir()
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE component_schema (component TEXT PRIMARY KEY, "
            "revision INTEGER NOT NULL, updated_at TEXT NOT NULL)"
        )
        db.commit()
    SQLiteStatePlane(path)
    return path


def test_multi_host_backup_requires_and_records_independent_verified_copies(tmp_path):
    state = make_state(tmp_path)
    plane = SQLiteStatePlane(state)
    coordinator = MultiHostBackupCoordinator(
        state_path=state,
        engine=BackupEngine(BackupCipher(b"k" * 32)),
        state_plane=plane,
        source_host_id="venus",
        source_failure_domain="desk-a",
        targets=(
            BackupTarget("artemis", "artemis", "rack-a", tmp_path / "a"),
            BackupTarget("eos", "eos", "rack-b", tmp_path / "b"),
        ),
        policy=BackupTopologyPolicy(
            minimum_copies=2,
            minimum_failure_domains=2,
            minimum_hosts=2,
            keep_per_target=2,
        ),
    )

    result = coordinator.run(now=NOW)

    assert result.accepted
    assert len(result.verified_copies) == 2
    assert {item.host_id for item in result.verified_copies} == {"artemis", "eos"}
    assert {item.failure_domain for item in result.verified_copies} == {
        "rack-a",
        "rack-b",
    }
    latest = BackupTopologyJournal(plane).latest()
    assert latest["set_id"] == result.set_id
    assert latest["accepted"] is True


def test_topology_preflight_rejects_same_source_failure_domain(tmp_path):
    state = make_state(tmp_path)
    coordinator = MultiHostBackupCoordinator(
        state_path=state,
        engine=BackupEngine(BackupCipher(b"k" * 32)),
        state_plane=SQLiteStatePlane(state),
        source_host_id="venus",
        source_failure_domain="desk-a",
        targets=(
            BackupTarget("copy-a", "artemis", "desk-a", tmp_path / "a"),
            BackupTarget("copy-b", "eos", "rack-b", tmp_path / "b"),
        ),
        policy=BackupTopologyPolicy(
            minimum_copies=2,
            minimum_failure_domains=2,
            minimum_hosts=2,
        ),
    )

    with pytest.raises(BackupTopologyError, match="outside source failure domain"):
        coordinator.run(now=NOW)


def test_failed_destination_is_journaled_and_policy_fails(tmp_path, monkeypatch):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    original = engine.create

    def create(**kwargs):
        if kwargs["failure_domain"] == "rack-b":
            raise OSError("target offline")
        return original(**kwargs)

    monkeypatch.setattr(engine, "create", create)
    plane = SQLiteStatePlane(state)
    coordinator = MultiHostBackupCoordinator(
        state_path=state,
        engine=engine,
        state_plane=plane,
        source_host_id="venus",
        source_failure_domain="desk-a",
        targets=(
            BackupTarget("artemis", "artemis", "rack-a", tmp_path / "a"),
            BackupTarget("eos", "eos", "rack-b", tmp_path / "b"),
        ),
        policy=BackupTopologyPolicy(
            minimum_copies=2,
            minimum_failure_domains=2,
            minimum_hosts=2,
        ),
    )

    with pytest.raises(BackupTopologyError, match="did not meet policy"):
        coordinator.run(now=NOW)

    latest = BackupTopologyJournal(plane).latest()
    assert latest["accepted"] is False
    assert {item["error_type"] for item in latest["copies"]} == {None, "OSError"}


@pytest.mark.parametrize("second", ["identical", "nested", "parent"])
def test_differently_labeled_targets_cannot_count_same_storage(tmp_path, second):
    state = make_state(tmp_path)
    a = tmp_path / "copies" / "one"
    b = {
        "identical": a,
        "nested": a / "child",
        "parent": a.parent,
    }[second]
    coordinator = MultiHostBackupCoordinator(
        state_path=state,
        engine=BackupEngine(BackupCipher(b"k" * 32)),
        state_plane=SQLiteStatePlane(state),
        source_host_id="venus",
        source_failure_domain="desk-a",
        targets=(
            BackupTarget("artemis", "artemis", "rack-a", a),
            BackupTarget("eos", "eos", "rack-b", b),
        ),
    )
    with pytest.raises(BackupTopologyError, match="share or overlap"):
        coordinator.run(now=NOW)


@pytest.mark.parametrize("target_root", ["state_home", "ancestor", "descendant"])
def test_backup_copy_may_not_write_inside_or_enclose_live_state(
    tmp_path, target_root,
):
    state = make_state(tmp_path)
    home = state.parent
    unsafe = {
        "state_home": home,
        "ancestor": tmp_path,
        "descendant": home / "nested",
    }[target_root]
    coordinator = MultiHostBackupCoordinator(
        state_path=state,
        engine=BackupEngine(BackupCipher(b"k" * 32)),
        state_plane=SQLiteStatePlane(state),
        source_host_id="venus",
        source_failure_domain="desk-a",
        targets=(
            BackupTarget("artemis", "artemis", "rack-a", unsafe),
            BackupTarget("eos", "eos", "rack-b", tmp_path / "independent"),
        ),
    )
    with pytest.raises(BackupTopologyError, match="overlaps canonical state"):
        coordinator.run(now=NOW)
