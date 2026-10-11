"""Cross-platform recovery manifest path validation, deferred tests."""
import pytest

from sofia.ops.backup import BackupEntry


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
