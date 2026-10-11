"""Deferred offline signed handoff against revoked authority and redirected assets.

Synthetic staged home and external broker only. No test execution or
active bootstrap pointer and no live host is touched.
"""
from dataclasses import replace
import sys

import pytest

from sofia.ops.state_promotion import prepare_pending_state_pointer
from test.test_ws2_pending_home_pointer_durability import _plan


def _prepare(staged, proof, pointer, verifier):
    return prepare_pending_state_pointer(
        staged=staged, authorization=proof, pointer_hmac_key=b"k" * 32,
        pending_path=pointer, minimum_next_epoch=2,
        verify_privileged_handoff=verifier,
    )


def test_privileged_approval_revoked_during_prepare_creates_no_pointer(tmp_path):
    staged, proof, trust = _plan(tmp_path)
    checks = []

    def independently_revoked(reviewed, source):
        checks.append((reviewed, source))
        return len(checks) == 1

    pending = trust / "handoff.pending.json"
    with pytest.raises(PermissionError, match="expired before pending"):
        _prepare(staged, proof, pending, independently_revoked)
    assert len(checks) == 2
    assert not pending.exists()
    assert (staged.destination_state_path.parent / "sofia.db").is_file()


@pytest.mark.skipif(
    not hasattr(__import__("os"), "symlink"), reason="symbolic links unavailable",
)
def test_staged_database_symlink_is_not_a_signable_verified_home(tmp_path):
    staged, proof, trust = _plan(tmp_path)
    database = staged.destination_state_path
    external = tmp_path / "other-db"
    external.write_bytes(b"fake outsider")
    database.unlink()
    try:
        database.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("file symlink creation denied by host")
    pending = trust / "handoff.pending.json"
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _prepare(staged, proof, pending, lambda *_a: True)
    assert not pending.exists()
    assert external.read_bytes() == b"fake outsider"


@pytest.mark.skipif(
    not hasattr(__import__("os"), "symlink"), reason="symbolic links unavailable",
)
def test_redirected_protected_identity_refuses_pending_pointer(tmp_path):
    staged, proof, trust = _plan(tmp_path)
    identity = staged.destination_state_path.parent / "protected" / "identity.json"
    outside = tmp_path / "external-owner-identity"
    outside.write_text('{"test":"outside"}')
    identity.unlink()
    try:
        identity.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("file symlink creation denied by host")
    pending = trust / "handoff.pending.json"
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _prepare(staged, proof, pending, lambda *_a: True)
    assert not pending.exists()
    assert outside.read_text() == '{"test":"outside"}'


def test_valid_source_and_still_approved_handoff_remains_nonactive(tmp_path):
    staged, proof, trust = _plan(tmp_path)
    calls = []
    pending = trust / "handoff.pending.json"

    def witness(reviewed, source):
        calls.append((reviewed, source))
        return reviewed is staged and source is proof

    result = _prepare(staged, proof, pending, witness)
    assert result.pending_path == pending
    assert result.activated is False
    assert len(calls) == 2
    assert pending.is_file()
