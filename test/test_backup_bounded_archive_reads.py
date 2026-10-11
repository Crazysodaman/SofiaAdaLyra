"""Deferred production backup verification bounds and recoverability tests.

Synthetic authenticated archive fixtures only. No live state or tests run.
"""
import pytest

from sofia.ops.backup import BackupCipher, BackupEngine, BackupError
from test.test_ops_backup_restore import NOW, make_state, make_erasure_journal


def _archive(tmp_path):
    state = make_state(tmp_path)
    engine = BackupEngine(BackupCipher(b"k" * 32))
    archive, _ = engine.create(
        state_path=state, destination_root=tmp_path / "backups",
        source_host_id="synthetic-owner",
        failure_domain="independent-fixture",
        now=NOW,
    )
    return engine, archive


def test_oversize_manifest_denied_before_authentication_parse(tmp_path):
    engine, archive = _archive(tmp_path)
    (archive / "manifest.json").write_bytes(b"x" * (16 * 1024 * 1024 + 1))
    with pytest.raises(BackupError, match="manifest exceeds bounded archive"):
        engine.verify(archive)


def test_oversize_authentication_record_denied_without_reading_as_text(tmp_path):
    engine, archive = _archive(tmp_path)
    (archive / "manifest.hmac").write_bytes(b"x" * 257)
    with pytest.raises(BackupError, match="authentication record exceeds size limit"):
        engine.verify(archive)


@pytest.mark.parametrize("extra", (b"padding", b""))
def test_corrupt_ciphertext_size_denied_before_decryption(tmp_path, monkeypatch, extra):
    engine, archive = _archive(tmp_path)
    payload = next((archive / "payload").glob("*.bin"))
    original = payload.read_bytes()
    payload.write_bytes(original + extra if extra else original[:-1])

    def no_decrypt(*_args, **_kwargs):
        raise AssertionError("unbounded or malformed encrypted payload was decrypted")

    monkeypatch.setattr(engine.cipher, "decrypt", no_decrypt)
    with pytest.raises(BackupError, match="encrypted payload size mismatch"):
        engine.verify(archive)


def test_restore_checks_second_payload_read_after_successful_verify(
    tmp_path, monkeypatch,
):
    engine, archive = _archive(tmp_path)
    original_verify = engine.verify

    def mutate_after_verification(directory):
        manifest = original_verify(directory)
        payload = next((directory / "payload").glob("*.bin"))
        payload.write_bytes(payload.read_bytes() + b"unsolicited bytes")
        return manifest

    monkeypatch.setattr(engine, "verify", mutate_after_verification)
    with pytest.raises(BackupError, match="restore encrypted payload size mismatch"):
        engine.restore(
            backup_dir=archive,
            target_state_path=tmp_path / "recovered" / "sofia.db",
            verifier="synthetic-fixture",
            erasure_journal=make_erasure_journal(tmp_path),
        )


def test_valid_archive_unchanged_by_bounded_read_policy(tmp_path):
    engine, archive = _archive(tmp_path)
    manifest = engine.verify(archive)
    assert "sofia.db" in {item.logical_path for item in manifest.entries}
