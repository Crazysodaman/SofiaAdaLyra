"""Deferred no-overwrite contracts for EVERY offline restored asset.

Uses only synthetic SQLite, encrypted archives and operator-journal fixtures.
"""
import os

import pytest

import sofia.platform.ops.backup as backup_module
from sofia.platform.ops.backup import (
    BackupCipher, BackupEngine, BackupError, RestorePublicationUncertain,
)
from sofia.platform.ops.restore_authority import ProtectedRestoreLedger
from test.test_ops_backup_restore import (
    NOW, make_erasure_journal, make_state, mint_replacement,
)


def _ready(tmp_path, monkeypatch):
    original = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(
        state_path=original,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus", failure_domain="offline-fixture",
    )
    journal = make_erasure_journal(tmp_path)
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )
    return engine, archive, journal


def test_absent_database_does_not_authorize_overwriting_existing_identity(
    tmp_path, monkeypatch,
):
    engine, archive, journal = _ready(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "sofia.db"
    protected = target.parent / "protected"
    protected.mkdir(parents=True)
    identity = protected / "identity.json"
    identity.write_bytes(b"existing-operator-identity")

    with pytest.raises(BackupError, match="explicit replace_existing"):
        engine.restore(
            backup_dir=archive, target_state_path=target,
            verifier="offline-reviewed", erasure_journal=journal,
        )

    assert identity.read_bytes() == b"existing-operator-identity"
    assert not target.exists()


def test_default_restore_never_replaces_file_created_during_publication(
    tmp_path, monkeypatch,
):
    engine, archive, journal = _ready(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "sofia.db"
    original_link = os.link
    collided = []

    def create_intervening_file(source, destination):
        if destination == target:
            destination.write_bytes(b"another-writer-owned-this-name")
            collided.append(destination)
        return original_link(source, destination)

    monkeypatch.setattr(backup_module.os, "link", create_intervening_file)
    # A protected asset can have been durably published before the
    # collision at the canonical database name. Keep that distinction
    # visible rather than reporting this as a cleanly aborted restore.
    with pytest.raises(RestorePublicationUncertain, match="part of the protected bundle"):
        engine.restore(
            backup_dir=archive, target_state_path=target,
            verifier="offline-reviewed", erasure_journal=journal,
        )

    assert collided == [target]
    assert target.read_bytes() == b"another-writer-owned-this-name"


def test_explicit_replace_existing_can_replace_verified_protected_assets(
    tmp_path, monkeypatch,
):
    engine, archive, journal = _ready(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "sofia.db"
    protected = target.parent / "protected"
    protected.mkdir(parents=True)
    identity = protected / "identity.json"
    identity.write_bytes(b"old-offline-identity")

    replacement = ProtectedRestoreLedger.initialize(
        tmp_path / "owner-ledger" / "restore-authority.db"
    )
    mint_replacement(replacement, target, engine.verify(archive))

    result = engine.restore(
        backup_dir=archive, target_state_path=target,
        verifier="operator-explicit-overwrite",
        replace_existing=True,
        now=NOW,
        erasure_journal=journal,
        replacement_authority=replacement,
    )

    assert result.succeeded
    assert target.is_file()
    assert identity.read_bytes() != b"old-offline-identity"


@pytest.mark.parametrize("database_name", (
    "personality.json", "PERSONALITY.JSON", "protected", "PROTECTED",
))
@pytest.mark.parametrize("replace_existing", (False, True))
def test_database_destination_cannot_alias_bundle_asset(
    tmp_path, monkeypatch, database_name, replace_existing,
):
    engine, archive, journal = _ready(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / database_name
    replacement = ProtectedRestoreLedger.initialize(
        tmp_path / "owner-ledger" / "restore-authority.db"
    )
    manifest = engine.verify(archive)
    mint_replacement(replacement, target, manifest)

    with pytest.raises(BackupError, match="database destination conflicts"):
        engine.restore(
            backup_dir=archive, target_state_path=target,
            verifier="offline-reviewed", erasure_journal=journal,
            replace_existing=replace_existing,
            replacement_authority=replacement if replace_existing else None,
            now=NOW,
        )

    # Reject before staging, consuming owner authority, or publishing assets.
    assert not target.parent.exists()
    replacement.require_replacement(target, manifest, now=NOW)


def test_distinct_custom_database_destination_preserves_bundle(tmp_path, monkeypatch):
    engine, archive, journal = _ready(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "restored.sqlite"
    result = engine.restore(
        backup_dir=archive, target_state_path=target,
        verifier="offline-reviewed", erasure_journal=journal,
    )
    assert result.succeeded
    assert target.read_bytes().startswith(b"SQLite format 3")
    assert (target.parent / "personality.json").read_bytes() == b"{}"
    assert (target.parent / "protected" / "identity.json").is_file()
