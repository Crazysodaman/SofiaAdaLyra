"""Deferred incomplete offline bundle publication classification contracts.

All archives, state and independently held journals are synthetic tmp_path
fixtures. Tests, CI and any live restore remain intentionally deferred.
"""
import os

import pytest

import sofia.platform.ops.backup as backup_module
from sofia.platform.ops.backup import (
    BackupCipher, BackupEngine, RestorePublicationUncertain,
)
from test.test_ops_backup_restore import make_erasure_journal, make_state


def _fixture(tmp_path, monkeypatch):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(
        state_path=state,
        destination_root=tmp_path / "encrypted",
        source_host_id="venus",
        failure_domain="offline-fixture",
    )
    monkeypatch.setattr(
        backup_module, "verify_production_component_schemas",
        lambda _path: None,
    )
    return engine, archive, make_erasure_journal(tmp_path), state


def test_second_asset_publish_failure_reports_uncertain_and_preserves_source(
    tmp_path, monkeypatch,
):
    engine, archive, journal, original = _fixture(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "sofia.db"
    original_link = os.link
    visible = []

    def fail_second_publication(src, dst):
        if visible:
            raise OSError("synthetic protected-bundle device failure")
        result = original_link(src, dst)
        visible.append(dst)
        return result

    monkeypatch.setattr(backup_module.os, "link", fail_second_publication)
    with pytest.raises(
        RestorePublicationUncertain, match="part of the protected bundle",
    ) as raised:
        engine.restore(
            backup_dir=archive, target_state_path=target,
            verifier="reviewed-offline-fixture", erasure_journal=journal,
        )
    assert isinstance(raised.value.__cause__, OSError)
    assert len(visible) == 1
    assert visible[0].is_file()
    assert original.is_file()
    assert engine.verify(archive).entries


def test_before_first_asset_publish_failure_does_not_claim_partial_restore(
    tmp_path, monkeypatch,
):
    engine, archive, journal, original = _fixture(tmp_path, monkeypatch)
    target = tmp_path / "recovered" / "sofia.db"

    def fail_initial_publication(_src, _dst):
        raise OSError("synthetic before-publish device failure")

    monkeypatch.setattr(backup_module.os, "link", fail_initial_publication)
    with pytest.raises(
        OSError, match="synthetic before-publish device failure",
    ):
        engine.restore(
            backup_dir=archive, target_state_path=target,
            verifier="reviewed-offline-fixture", erasure_journal=journal,
        )
    assert original.is_file()
    assert not target.exists()
    assert not (target.parent / "protected" / "identity.json").exists()
