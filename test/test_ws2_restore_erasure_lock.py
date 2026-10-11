"""Deferred full offline restore versus signed erasure append lock contract.

Synthetic encrypted archives only; never run against an active state home.
"""
from contextlib import contextmanager
import os

import sofia.memory.deletion_ledger as journal_module
import sofia.ops.backup as backup_module
from sofia.ops.backup import BackupCipher, BackupEngine
from test.test_ops_backup_restore import make_erasure_journal, make_state


def test_file_by_file_restore_publication_keeps_erasure_append_fenced(
    tmp_path, monkeypatch,
):
    original = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _evidence = engine.create(
        state_path=original,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus", failure_domain="offline-fixture",
    )
    journal = make_erasure_journal(tmp_path)
    destination = tmp_path / "restored" / "sofia.db"
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _state: None,
    )
    held = [False]
    published_while_locked = []
    underlying_lock = journal_module.MemoryDeletionLedger._exclusive
    underlying_replace = os.replace

    @contextmanager
    def observe_lock(self):
        with underlying_lock(self):
            assert not held[0]
            held[0] = True
            try:
                yield
            finally:
                held[0] = False

    def observe_replace(source, target):
        if destination.parent in target.parents:
            published_while_locked.append(held[0])
        elif target == destination:
            published_while_locked.append(held[0])
        return underlying_replace(source, target)

    monkeypatch.setattr(
        journal_module.MemoryDeletionLedger, "_exclusive", observe_lock,
    )
    monkeypatch.setattr(backup_module.os, "replace", observe_replace)

    receipt = engine.restore(
        backup_dir=archive,
        target_state_path=destination,
        verifier="offline-recovery-review",
        erasure_journal=journal,
    )
    assert receipt.succeeded is True
    assert destination.is_file()
    assert published_while_locked and all(published_while_locked)
    assert held == [False]
