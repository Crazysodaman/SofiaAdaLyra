"""Deferred offline signed pending-pointer crash durability and path contracts.

All state homes and pointer files here are synthetic tmp_path fixtures.
No active bootstrap pointer or real host is opened.
"""
import json
import sys

import pytest

import sofia.platform.ops.state_promotion as promotion
from sofia.platform.ops.state_promotion import (
    PendingHomePointerUncertain, prepare_pending_state_pointer,
)
from sofia.platform.ops.state_relocation import RelocationAuthorization, StagedStateHome


def _plan(tmp_path):
    home = tmp_path / "staged"
    (home / "protected").mkdir(parents=True)
    (home / "sofia.db").write_bytes(b"synthetic-only")
    (home / "protected" / "identity.json").write_text("{}")
    trust = tmp_path / "trusted"
    trust.mkdir()
    proof = RelocationAuthorization(
        source_state_path=tmp_path / "original" / "sofia.db",
        destination_root=home,
        writer_host_id="Artemis:sofia",
        source_writer_host_id="Venus",
        next_writer_epoch=2,
        operator_approval_ref="operator-reviewed",
        writer_fence_ref="privileged-fence-evidence",
        protected_operation_id="offline:supervised-venus-artemis-fixture",
        operator_principal_id="owner:supervised-fixture",
        source_writer_epoch=1,
    )
    staged = StagedStateHome(
        backup_dir=tmp_path / "encrypted-backup",
        destination_state_path=home / "sofia.db",
        backup_id="backup-verified",
        writer_host_id="Artemis:sofia",
        proposed_writer_epoch=2,
        verified_restore=True,
    )
    return staged, proof, trust


def _prepare(staged, proof, pointer):
    return prepare_pending_state_pointer(
        staged=staged, authorization=proof,
        pointer_hmac_key=b"k" * 32,
        pending_path=pointer, minimum_next_epoch=2,
        verify_privileged_handoff=lambda received, authorized:
            received is staged and authorized is proof,
    )


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory fsync")
def test_pending_pointer_syncs_its_trusted_parent_after_persisting_bytes(
    tmp_path, monkeypatch,
):
    staged, proof, trust = _plan(tmp_path)
    pending = trust / "handoff.pending.json"
    actual = promotion._fsync_linux_entry
    seen = []

    def track_sync(path, *, directory):
        seen.append((path, directory, pending.exists()))
        return actual(path, directory=directory)

    monkeypatch.setattr(promotion, "_fsync_linux_entry", track_sync)
    outcome = _prepare(staged, proof, pending)
    assert outcome.pending_path == pending
    assert not outcome.activated
    assert seen == [(trust, True, True)]
    assert json.loads(pending.read_text())["epoch"] == 2


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux directory fsync")
def test_uncertain_directory_flush_keeps_original_signed_pending_bytes(
    tmp_path, monkeypatch,
):
    staged, proof, trust = _plan(tmp_path)
    pending = trust / "handoff.pending.json"

    def deny_parent_sync(_path, *, directory):
        assert directory
        raise OSError("synthetic durability failure")

    monkeypatch.setattr(promotion, "_fsync_linux_entry", deny_parent_sync)
    with pytest.raises(PendingHomePointerUncertain, match="uncertain"):
        _prepare(staged, proof, pending)
    assert json.loads(pending.read_text())["writer_host_id"] == "Artemis:sofia"
    with pytest.raises(FileExistsError, match="never overwrite"):
        _prepare(staged, proof, pending)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="symlink creation")
def test_pending_pointer_refuses_redirected_trust_parent(
    tmp_path,
):
    staged, proof, trust = _plan(tmp_path)
    redirect = tmp_path / "redirected"
    redirect.symlink_to(trust, target_is_directory=True)
    with pytest.raises(PermissionError, match="symbolic link or junction"):
        _prepare(staged, proof, redirect / "handoff.pending.json")
    assert not (trust / "handoff.pending.json").exists()
