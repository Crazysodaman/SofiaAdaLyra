"""Deferred signed memory deletion approval revocation before journal append.

Only synthetic journal data and independent approval callbacks; tests are
not executed, and no real user memory or backup is changed.
"""
from datetime import datetime, timezone
from uuid import UUID

import pytest

from sofia.core.memory.deletion_ledger import MemoryDeletionLedger
from sofia.platform.ops.backup import BackupCipher


CANDIDATE = UUID("aaaaaaaa-1111-4111-8111-111111111111")
NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _request(ledger, approve):
    return ledger.request(
        candidate_id=CANDIDATE, principal_id="person:sparks",
        audience_id="local:text", authority_ref="operator:reviewed-erasure",
        at=NOW, approve=approve,
    )


def test_revoked_independent_approval_before_append_writes_no_tombstone(tmp_path):
    journal = MemoryDeletionLedger(
        tmp_path / "erasure.jsonl", BackupCipher(b"k" * 32),
    )
    journal.initialize()
    baseline = journal.path.read_bytes()
    approvals = []

    def owner_witness(candidate, principal, audience, reference):
        approvals.append((candidate, principal, audience, reference))
        return len(approvals) == 1

    with pytest.raises(PermissionError, match="expired before append"):
        _request(journal, owner_witness)

    assert len(approvals) == 2
    assert journal.entries() == ()
    assert journal.path.read_bytes() == baseline


def test_independently_confirmed_erasure_still_appends_exactly_once(tmp_path):
    journal = MemoryDeletionLedger(
        tmp_path / "erasure.jsonl", BackupCipher(b"k" * 32),
    )
    journal.initialize()
    witness = []

    def owner_witness(candidate, principal, audience, reference):
        witness.append((candidate, principal, audience, reference))
        return True

    assert _request(journal, owner_witness) is True
    assert len(witness) == 2
    assert len(journal.entries()) == 1
    assert _request(journal, owner_witness) is False
    assert len(journal.entries()) == 1
