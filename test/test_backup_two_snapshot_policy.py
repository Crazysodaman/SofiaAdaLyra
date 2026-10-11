"""Operator-approved two-snapshot retention without invoking live backups.

Acceptance source only. Tests are intentionally not executed during coding.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.ops import backup_cli
from sofia.ops.backup import BackupCipher, BackupEngine, BackupError, rotate_backups
from sofia.ops.backup_topology import BackupTopologyPolicy
from test.test_ops_backup_restore import make_state


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _archives(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    ))


def test_owner_policy_retains_two_per_independent_backup_target():
    """Target-local generations are separate from cross-host copy count."""
    policy = BackupTopologyPolicy()
    assert policy.keep_per_target == 2
    assert policy.minimum_copies == 2
    assert policy.minimum_failure_domains == 2
    assert policy.minimum_hosts == 2


def test_backup_create_verifies_then_keeps_two_snapshots(tmp_path, monkeypatch):
    state = make_state(tmp_path)
    root = tmp_path / "isolated-backups"
    engine = BackupEngine(BackupCipher(b"k" * 32))
    oldest, _ = engine.create(
        state_path=state, destination_root=root,
        source_host_id="venus", failure_domain="isolated",
        now=NOW,
    )
    recent, _ = engine.create(
        state_path=state, destination_root=root,
        source_host_id="venus", failure_domain="isolated",
        now=NOW + timedelta(days=1),
    )
    assert len(_archives(root)) == 2
    key = tmp_path / "key.bin"
    key.write_bytes(b"k" * 32)
    monkeypatch.setattr(
        backup_cli, "datetime",
        SimpleNamespace(now=lambda _tz: NOW + timedelta(days=2)),
    )
    code = backup_cli.main([
        "create", "--key", str(key), "--destination", str(root),
        "--failure-domain", "isolated", "--state-path", str(state),
        "--source-host", "venus",
    ])
    assert code == 0
    kept = _archives(root)
    assert len(kept) == 2
    assert oldest not in kept
    assert recent in kept
    assert all(engine.verify(path).failure_domain == "isolated" for path in kept)


def test_backup_creation_cannot_prune_if_new_archive_verification_fails(
    tmp_path, monkeypatch,
):
    """Verification failure leaves previously retained recovery copies intact."""
    state = make_state(tmp_path)
    root = tmp_path / "isolated-backups"
    engine = BackupEngine(BackupCipher(b"k" * 32))
    original = tuple(engine.create(
        state_path=state, destination_root=root,
        source_host_id="venus", failure_domain="isolated",
        now=NOW + timedelta(days=day),
    )[0] for day in (0, 1))
    key = tmp_path / "key.bin"
    key.write_bytes(b"k" * 32)
    monkeypatch.setattr(
        backup_cli, "datetime",
        SimpleNamespace(now=lambda _tz: NOW + timedelta(days=2)),
    )
    monkeypatch.setattr(
        BackupEngine, "verify",
        lambda self, _path: (_ for _ in ()).throw(
            RuntimeError("deliberately unavailable archive verification")
        ),
    )
    assert backup_cli.main([
        "create", "--key", str(key), "--destination", str(root),
        "--failure-domain", "isolated", "--state-path", str(state),
        "--source-host", "venus",
    ]) == 2
    assert all(path.exists() for path in original)
    # The incomplete attempt may exist for operator review, but neither
    # original is auto-pruned on any failed verification.
    assert len(_archives(root)) >= 2


def test_manual_rotation_defaults_to_two_without_touching_other_files(
    tmp_path,
):
    root = tmp_path / "backup-home"
    root.mkdir()
    by_name = []
    for i in range(3):
        item = root / f"2026100{i+1}T120000Z-fixture"
        item.mkdir()
        (item / "manifest.json").write_text("{}", encoding="utf-8")
        by_name.append(item)
    journal = root / "operator-erasure-marker.txt"
    journal.write_text("not a snapshot", encoding="utf-8")
    assert backup_cli.main([
        "rotate", "--root", str(root),
    ]) == 0
    assert not by_name[0].exists()
    assert all(x.exists() for x in by_name[1:])
    assert journal.read_text(encoding="utf-8") == "not a snapshot"


def test_automatic_rotation_rejects_corrupt_old_copy_without_deleting_anything(
    tmp_path,
):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    root = tmp_path / "encrypted"
    copies = tuple(engine.create(
        state_path=state, destination_root=root, source_host_id="venus",
        failure_domain="offline-fixture", now=NOW + timedelta(days=i),
    )[0] for i in range(3))
    first_payload = next((copies[0] / "payload").iterdir())
    first_payload.write_bytes(b"corrupt-old-generation")
    with pytest.raises(BackupError):
        rotate_backups(
            root, keep=2, verifier=engine.verify,
            expected_source_host_id="venus",
            expected_failure_domain="offline-fixture",
        )
    assert all(copy.is_dir() for copy in copies)
    assert engine.verify(copies[2]).source_host_id == "venus"


def test_automatic_rotation_refuses_foreign_backup_source_without_deletion(
    tmp_path,
):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    root = tmp_path / "encrypted"
    first, _ = engine.create(
        state_path=state, destination_root=root, source_host_id="other-host",
        failure_domain="offline-fixture", now=NOW,
    )
    second, _ = engine.create(
        state_path=state, destination_root=root, source_host_id="venus",
        failure_domain="offline-fixture", now=NOW + timedelta(days=1),
    )
    third, _ = engine.create(
        state_path=state, destination_root=root, source_host_id="venus",
        failure_domain="offline-fixture", now=NOW + timedelta(days=2),
    )
    with pytest.raises(BackupError, match="different source owner"):
        rotate_backups(
            root, keep=2, verifier=engine.verify,
            expected_source_host_id="venus",
            expected_failure_domain="offline-fixture",
        )
    assert all(path.is_dir() for path in (first, second, third))


def test_authenticated_rotation_prunes_only_after_every_copy_verifies(tmp_path):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    root = tmp_path / "encrypted"
    copies = tuple(engine.create(
        state_path=state, destination_root=root, source_host_id="venus",
        failure_domain="offline-fixture", now=NOW + timedelta(days=i),
    )[0] for i in range(3))
    removed = rotate_backups(
        root, keep=2, verifier=engine.verify,
        expected_source_host_id="venus",
        expected_failure_domain="offline-fixture",
    )
    assert removed == (copies[0],)
    assert not copies[0].exists()
    assert all(engine.verify(copy).source_host_id == "venus" for copy in copies[1:])
