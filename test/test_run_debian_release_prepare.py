"""Debian update installer staging must be root-scoped, signed and nonactivating."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from sofia.run import debian_release_prepare as prepare


SHA = "a" * 40
DIGEST = "b" * 64


def _paths(tmp_path, monkeypatch, version):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "release-1").mkdir()
    artifacts = inbox / "release-1" / "artifact"
    artifacts.mkdir()
    (artifacts / "sofia_ada_lyra-0.1.0-py3-none-any.whl").write_bytes(b"test")
    (artifacts / "requirements.lock").write_bytes(b"test")
    envs = tmp_path / "release-environments"
    envs.mkdir()
    key = tmp_path / "release-key.pem"
    key.write_bytes(b"test public key")
    manifest = SimpleNamespace(
        release_id="release-1", git_revision=SHA,
        manifest_sha256=DIGEST, python_version=version,
        artifact_sha256="c" * 64, application_version="0.1.0",
    )
    monkeypatch.setattr(prepare, "require_debian_guest", lambda: None)
    monkeypatch.setattr(prepare.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(prepare, "_root_owned_directory", lambda _: None)
    monkeypatch.setattr(prepare, "verified_inbox_release", lambda **_:
        SimpleNamespace(revision=SHA, release_id="release-1", manifest_sha256=DIGEST))
    monkeypatch.setattr(prepare, "verify_release_evidence", lambda path: manifest)
    # This test exercises the pre-install gates. Never invoke actual pip.
    return inbox, envs, key


def test_windows_python_release_is_rejected_before_venv_changes(tmp_path, monkeypatch):
    incompatible = "3.12.10" if sys.version_info[:2] != (3, 12) else "3.13.5"
    inbox, envs, key = _paths(tmp_path, monkeypatch, incompatible)
    class NoInstaller:
        def __init__(self, **kwargs):
            pytest.fail("incompatible platform must not invoke installer")
    monkeypatch.setattr(prepare, "ReleaseEnvironmentManager", NoInstaller)
    with pytest.raises(prepare.DebianReleasePrepareError, match="Python version"):
        prepare.prepare_candidate(
            inbox=inbox, trusted_key=key, signer_key_id="prod",
            revision=SHA, environments=envs,
        )


def test_exact_signed_python_release_prepares_without_activation(tmp_path, monkeypatch):
    version = ".".join(map(str, sys.version_info[:2])) + ".0"
    inbox, envs, key = _paths(tmp_path, monkeypatch, version)
    installed = []
    class Installer:
        def __init__(self, *, release_root, environments_root):
            assert release_root == inbox / "release-1"
            assert environments_root == envs
        def ensure(self, candidate):
            installed.append(candidate)
            return SimpleNamespace(
                root=envs / "release-1",
                python_path=envs / "release-1" / "bin" / "python",
            )
    monkeypatch.setattr(prepare, "ReleaseEnvironmentManager", Installer)
    result = prepare.prepare_candidate(
        inbox=inbox, trusted_key=key, signer_key_id="prod",
        revision=SHA, environments=envs,
    )
    assert installed[0].manifest_sha256 == DIGEST
    assert result.activated is False
    assert result.restarted is False
    assert result.release_id == "release-1"
    assert not (tmp_path / "sofia.db").exists()


def test_unprivileged_process_cannot_stage_release(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "require_debian_guest", lambda: None)
    monkeypatch.setattr(prepare.os, "geteuid", lambda: 1000, raising=False)
    with pytest.raises(PermissionError, match="privileged"):
        prepare.prepare_candidate(
            inbox=tmp_path, trusted_key=tmp_path / "key",
            signer_key_id="prod", revision=SHA,
        )


def test_invalid_source_revision_is_not_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "require_debian_guest", lambda: None)
    monkeypatch.setattr(prepare.os, "geteuid", lambda: 0, raising=False)
    with pytest.raises(ValueError, match="exact"):
        prepare.prepare_candidate(
            inbox=tmp_path, trusted_key=tmp_path / "key",
            signer_key_id="prod", revision="main",
        )


def test_trusted_signer_gate_refuses_missing_or_redirected_public_key(tmp_path):
    # Root signing trust cannot be inferred from a filename or a test stub.
    missing = tmp_path / "missing-key.pem"
    with pytest.raises(PermissionError, match="root-owned release signer"):
        prepare._require_root_owned_signer_key(missing)
    target = tmp_path / "real-key.pem"
    target.write_bytes(b"untrusted")
    redirected = tmp_path / "redirected-key.pem"
    try:
        redirected.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this host")
    with pytest.raises(PermissionError, match="root-owned release signer"):
        prepare._require_root_owned_signer_key(redirected)
