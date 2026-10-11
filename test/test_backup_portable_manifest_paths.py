"""Cross-platform recovery manifest path validation, deferred tests."""
from datetime import datetime, timezone
import pytest

from sofia.ops.backup import BackupEntry, BackupManifest


def _entry(logical="protected/identity.json", payload="0000.bin"):
    return BackupEntry(
        logical_path=logical, payload_name=payload,
        sha256="a" * 64, size=1, nonce_b64="AA==",
    )


@pytest.mark.parametrize("bad", (
    "../escape.txt", "protected/../../escape", "/tmp/escape",
    "C:/Windows/System32", "D:relative.txt",
    "protected//identity.json", "protected/./identity.json",
    "protected/../identity.json", ".", "",
    "protected/CON", "protected/AUX",
    "protected/bad?name", "protected/bad|name",
    "protected" + chr(92) + ".." + chr(92) + "escape.txt",
    chr(92) + chr(92) + "server" + chr(92) + "share",
    "safe" + chr(0) + "unsafe",
))
def test_malformed_manifest_logical_path_rejected_on_every_os(bad):
    with pytest.raises(ValueError, match="safe relative"):
        _entry(logical=bad)


@pytest.mark.parametrize("bad", (
    "../0000.bin", "a/0000.bin", "C:0000.bin", "CON",
    "bad?name.bin", "bad|name.bin", "",
    "..", ".", "foo" + chr(92) + "bar",
    "name" + chr(0) + ".bin",
))
def test_malformed_manifest_payload_name_rejected_on_every_os(bad):
    with pytest.raises(ValueError, match="simple file name"):
        _entry(payload=bad)


def test_legitimate_canonical_bundle_paths_remain_accepted():
    for name in (
        "sofia.db", "protected/constitution.md",
        "protected/identity.json", "personality.json",
        "avatar.json", "release-runtime/active-release.json",
    ):
        assert _entry(logical=name).logical_path == name

@pytest.mark.parametrize("bad", (
    "protected/name.", "protected/name ", "protected/name" + chr(9) + "bad",
    "protected/unsafe.", "protected/unsafe ",
))
def test_manifest_rejects_platform_normalized_or_control_names(bad):
    with pytest.raises(ValueError, match="safe relative"):
        _entry(logical=bad)


@pytest.mark.parametrize("bad", ("payload.", "payload ", "payload" + chr(10) + "name"))
def test_manifest_rejects_nonportable_payload_aliases(bad):
    with pytest.raises(ValueError, match="simple file name"):
        _entry(payload=bad)


def _manifest(*entries):
    return BackupManifest(
        backup_id="backup-1",
        source_host_id="fixture-owner",
        failure_domain="separate-recovery-fixture",
        created_at=datetime(2026, 10, 11, tzinfo=timezone.utc),
        entries=entries,
    )


def test_backup_manifest_rejects_windows_casefold_logical_collision():
    with pytest.raises(ValueError, match="portable-unique"):
        _manifest(
            _entry(logical="protected/Identity.json", payload="0001.bin"),
            _entry(logical="protected/identity.json", payload="0002.bin"),
        )


def test_backup_manifest_rejects_windows_casefold_payload_collision():
    with pytest.raises(ValueError, match="portable-unique"):
        _manifest(
            _entry(logical="protected/identity.json", payload="PART.bin"),
            _entry(logical="protected/personality.json", payload="part.bin"),
        )


def test_backup_manifest_accepts_distinct_portable_recovery_paths():
    assert len(_manifest(
        _entry(logical="protected/identity.json", payload="0001.bin"),
        _entry(logical="protected/personality.json", payload="0002.bin"),
    ).entries) == 2
