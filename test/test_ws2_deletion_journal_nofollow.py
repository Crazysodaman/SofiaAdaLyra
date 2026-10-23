"""Deferred external deletion-journal no-follow and inode fencing regressions.

Local tmp_path fixtures only; these contracts are authored, not executed.
"""
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

import pytest

import sofia.core.memory.deletion_ledger as journal_module
from sofia.core.memory.deletion_ledger import MemoryDeletionLedger, MemoryErasureError
from sofia.platform.ops.backup import BackupCipher


def _journal(tmp_path):
    ledger = MemoryDeletionLedger(
        tmp_path / "erasure.jsonl", BackupCipher(b"k" * 32),
    )
    ledger.initialize()
    return ledger


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="no O_NOFOLLOW support")
def test_external_lock_symlink_is_not_followed_or_modified(tmp_path):
    ledger = _journal(tmp_path)
    outside = tmp_path / "unrelated-owner-evidence"
    outside.write_bytes(b"unchanged")
    lock = ledger.path.with_suffix(ledger.path.suffix + ".lock")
    lock.symlink_to(outside)

    with pytest.raises(MemoryErasureError, match="redirected journal lock"):
        with ledger._exclusive():
            pytest.fail("symlinked append lock must never authorize operations")
    assert outside.read_bytes() == b"unchanged"
    assert ledger.entries() == ()


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="no O_NOFOLLOW support")
def test_append_refuses_journal_substituted_during_final_open(
    tmp_path, monkeypatch,
):
    ledger = _journal(tmp_path)
    original_bytes = ledger.path.read_bytes()
    outside = tmp_path / "foreign-secret"
    outside.write_bytes(b"must-survive")
    raw_open = os.open
    replaced = []

    def swap_before_append(path, flags, *args, **kwargs):
        if os.fspath(path) == os.fspath(ledger.path) and flags & os.O_APPEND:
            replacement = ledger.path.with_suffix(".old")
            ledger.path.rename(replacement)
            ledger.path.symlink_to(outside)
            replaced.append(replacement)
        return raw_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(journal_module.os, "open", swap_before_append)
    with pytest.raises(OSError):
        ledger.request(
            candidate_id=UUID("aaaaaaaa-1111-4111-8111-111111111111"),
            principal_id="person:sparks",
            audience_id="local:text",
            authority_ref="operator:approved-erasure",
            at=datetime(2026, 10, 11, tzinfo=timezone.utc),
            approve=lambda *_args: True,
        )

    assert replaced
    assert replaced[0].read_bytes() == original_bytes
    assert outside.read_bytes() == b"must-survive"


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="no O_NOFOLLOW support")
def test_append_preserves_original_hmac_chain_and_idempotency(tmp_path):
    ledger = _journal(tmp_path)
    request = dict(
        candidate_id=UUID("aaaaaaaa-1111-4111-8111-111111111111"),
        principal_id="person:sparks",
        audience_id="local:text",
        authority_ref="operator:approved-erasure",
        at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        approve=lambda *_args: True,
    )
    assert ledger.request(**request) is True
    assert ledger.request(**request) is False
    assert len(ledger.entries()) == 1
