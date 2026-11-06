"""Protected restore replacement authority contracts (G5).

An existing protected state home may only be replaced through an
operator-owned single-use receipt that binds the exact destination pathname
and the exact authenticated backup manifest, while an active operator STOP
and every placement rule deny the publication outright.
"""
from test.owner_auth_fixture import record_verified_restore_receipt, revoke_verified_restore_receipt
from datetime import timedelta
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from sofia.platform.safe.audit import AuditChain
from sofia.platform.ops.backup import BackupCipher, BackupEngine, BackupError
from sofia.platform.ops.restore_authority import (
    ProtectedRestoreLedger,
    ProtectedRestoreReplacementApproval,
    RestoreAuthorityUnavailable,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from test.test_ops_backup_restore import (
    NOW,
    make_erasure_journal,
    make_restore_authority,
    make_state,
    mint_replacement,
)


class _StubManifest:
    backup_id = "20261003-stub-backup"
    digest = "b" * 64


@pytest.fixture
def engine():
    return BackupEngine(BackupCipher(b"k" * 32))


@pytest.fixture
def stub_manifest():
    return _StubManifest()


def _archive(tmp_path, engine):
    state = make_state(tmp_path)
    archive, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "backups",
        source_host_id="venus",
        failure_domain="external-disk",
        now=NOW,
    )
    return engine.verify(archive), archive


def _wire(tmp_path, engine, monkeypatch):
    manifest, archive = _archive(tmp_path, engine)
    monkeypatch.setattr(
        "sofia.platform.ops.backup.verify_production_component_schemas",
        lambda _path: None,
    )
    journal = make_erasure_journal(tmp_path)
    return manifest, archive, journal


def _receipt(
    target: Path | str,
    manifest,
    *,
    approval_id: str,
    approved_at=None,
    expires_at=None,
) -> ProtectedRestoreReplacementApproval:
    return ProtectedRestoreReplacementApproval(
        approval_id=approval_id,
        target_state_path=str(Path(target).absolute()),
        backup_id=manifest.backup_id,
        manifest_digest=manifest.digest,
        approved_by="Sparks",
        approved_at=approved_at or NOW - timedelta(seconds=30),
        expires_at=expires_at or NOW + timedelta(hours=2),
    )


def test_ledger_never_manufactures_itself(tmp_path):
    path = tmp_path / "owner-ledger" / "restore-authority.db"

    with pytest.raises(RestoreAuthorityUnavailable):
        ProtectedRestoreLedger(path)

    ledger = ProtectedRestoreLedger.initialize(path)
    assert ProtectedRestoreLedger(path).path == ledger.path
    verified, reason = AuditChain(path).verify()
    assert verified is True
    assert reason is None


def test_receipt_identity_is_immutable(tmp_path, stub_manifest):
    ledger = make_restore_authority(tmp_path)
    target = str(tmp_path / "restore" / "sofia.db")

    record_verified_restore_receipt(ledger, _receipt(target, stub_manifest, approval_id="restore.dup"))
    with pytest.raises(PermissionError, match="immutable"):
        record_verified_restore_receipt(ledger, _receipt(target, stub_manifest, approval_id="restore.dup"))


def test_engine_rejects_missing_or_improvised_authority(tmp_path, engine, monkeypatch):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    target = tmp_path / "restored" / "sofia.db"

    with pytest.raises(BackupError, match="owner restore authority ledger"):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
        )

    class _Impostor:
        def authorize(self, *args, **kwargs):
            return True

    replacement = make_restore_authority(tmp_path)
    with pytest.raises(TypeError, match="ProtectedRestoreLedger"):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=_Impostor(),
        )
    assert ledger_is_untouched(replacement)


def ledger_is_untouched(ledger: ProtectedRestoreLedger) -> bool:
    return ledger.active_receipts(now=NOW) == ()


def test_denied_replacement_leaves_the_destination_alone(tmp_path, engine, monkeypatch):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    foreign = _StubManifest()
    target = tmp_path / "restored" / "sofia.db"
    ledger = make_restore_authority(tmp_path)
    mint_replacement(ledger, target, foreign)

    with pytest.raises(
        BackupError, match="no receipt was recorded for this exact replacement",
    ):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )

    assert not target.exists()
    # A refusal never consumes a receipt: the recorded approval is still
    # available for the operator's corrected attempt.
    receipt = ledger.active_receipts(now=NOW)
    assert len(receipt) == 1
    assert receipt[0].approval_id == "restore.replacement-1"


def test_expired_or_revoked_receipts_deny_replacement(tmp_path, engine, monkeypatch):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    target = tmp_path / "restored" / "sofia.db"
    ledger = make_restore_authority(tmp_path)

    record_verified_restore_receipt(ledger,
        _receipt(
            target, manifest, approval_id="restore.expired",
            approved_at=NOW - timedelta(hours=3),
            expires_at=NOW - timedelta(hours=1),
        )
    )
    with pytest.raises(BackupError, match="receipt window has expired"):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    assert not target.exists()

    approval = mint_replacement(
        ledger, target, manifest, approval_id="restore.revoke-me",
    )
    revoke_verified_restore_receipt(ledger, approval.approval_id, reason="owner retraction", at=NOW)
    with pytest.raises(BackupError, match="receipt was revoked"):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    assert not target.exists()
    assert ledger.active_receipts(now=NOW) == ()


def test_operator_stop_freezes_between_receipt_and_publication(
    tmp_path, engine, monkeypatch,
):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    home = tmp_path / "destination-home"
    home.mkdir()
    target = make_state(home)
    ledger = make_restore_authority(tmp_path)
    mint_replacement(ledger, target, manifest)

    OperatorStopStore(target).set(
        active=True, updated_by="Sparks",
        reason="frozen owner review", at=NOW,
    )
    with pytest.raises(BackupError, match="destination operator stop is active"):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    assert target.stat().st_size > 0
    # The stopped destination consumed nothing: the receipt still exists.
    frozen_receipt = ledger.active_receipts(now=NOW)
    assert len(frozen_receipt) == 1
    assert frozen_receipt[0].approval_id == "restore.replacement-1"

    # A destination without an engaged operator stop publishes normally.
    free_home = tmp_path / "stop-free-home"
    free_home.mkdir()
    free_target = make_state(free_home)
    mint_replacement(
        ledger, free_target, manifest, approval_id="restore.stop-free",
    )
    result = engine.restore(
        backup_dir=archive, target_state_path=free_target, verifier="test",
        replace_existing=True, now=NOW, erasure_journal=journal,
        replacement_authority=ledger,
    )
    assert result.succeeded is True
    with closing(sqlite3.connect(free_target)) as db, db:
        assert db.execute(
            "SELECT value FROM state_plane_meta WHERE key='schema_revision'"
        ).fetchone() == ("1",)
    remaining = ledger.active_receipts(now=NOW)
    assert [receipt.approval_id for receipt in remaining] == [
        "restore.replacement-1",
    ]


def test_unverifiable_destination_bytes_fail_the_stop_check(
    tmp_path, engine, monkeypatch,
):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    target = tmp_path / "restored" / "sofia.db"
    target.parent.mkdir()
    target.write_bytes(b"foreign-unidentifiable-protected-bytes")
    ledger = make_restore_authority(tmp_path)
    mint_replacement(ledger, target, manifest)

    with pytest.raises(
        BackupError, match="operator-stop verification is unavailable",
    ):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    assert target.read_bytes() == b"foreign-unidentifiable-protected-bytes"


def test_authority_ledger_cannot_live_inside_what_it_replaces(
    tmp_path, engine, monkeypatch,
):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    home = tmp_path / "restored"
    home.mkdir()
    target = home / "sofia.db"
    ledger = ProtectedRestoreLedger.initialize(home / "restore-authority.db")
    mint_replacement(ledger, target, manifest)

    with pytest.raises(
        BackupError,
        match="ledger must live outside the restored state and backup",
    ):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    assert not target.exists()


def test_active_receipts_expose_only_usable_windows(tmp_path, stub_manifest):
    ledger = make_restore_authority(tmp_path)
    live = _receipt(
        tmp_path / "restore-one" / "sofia.db", stub_manifest,
        approval_id="restore.live",
    )
    past = _receipt(
        tmp_path / "restore-two" / "sofia.db", stub_manifest,
        approval_id="restore.past",
        approved_at=NOW - timedelta(hours=3),
        expires_at=NOW - timedelta(hours=1),
    )
    record_verified_restore_receipt(ledger, live)
    record_verified_restore_receipt(ledger, past)

    assert [
        receipt.approval_id
        for receipt in ledger.active_receipts(now=NOW)
    ] == ["restore.live"]

    revoke_verified_restore_receipt(ledger, "restore.live", reason="test revocation", at=NOW)
    assert ledger.active_receipts(now=NOW) == ()


def test_owner_decisions_stay_in_the_append_only_evidence(
    tmp_path, engine, monkeypatch,
):
    manifest, archive, journal = _wire(tmp_path, engine, monkeypatch)
    target = tmp_path / "restored" / "sofia.db"
    ledger = make_restore_authority(tmp_path)

    # A refusal is owner evidence, not a silent no-op.
    with pytest.raises(BackupError):
        engine.restore(
            backup_dir=archive, target_state_path=target, verifier="test",
            replace_existing=True, now=NOW, erasure_journal=journal,
            replacement_authority=ledger,
        )
    mint_replacement(ledger, target, manifest)
    result = engine.restore(
        backup_dir=archive, target_state_path=target, verifier="test",
        replace_existing=True, now=NOW, erasure_journal=journal,
        replacement_authority=ledger,
    )
    assert result.succeeded is True

    verified, reason = AuditChain(ledger.path).verify()
    assert verified is True
    assert reason is None
    with sqlite3.connect(ledger.path) as db:
        events = db.execute(
            "SELECT event_type FROM safe_audit_event ORDER BY sequence"
        ).fetchall()
    types = [row[0] for row in events]
    assert types == [
        "ops.restore.replacement.denied",
        "owner.webauthn.verified",
        "execution.approval.recorded",
        "ops.restore.replacement.recorded",
        "execution.approval.consumed",
        "ops.restore.replacement.consumed",
    ]
