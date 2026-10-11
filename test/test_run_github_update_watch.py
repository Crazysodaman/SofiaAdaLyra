"""Independent GitHub discovery and signed-bundle admission regression gates.

No network, canonical database, systemd, or host update is started by tests.
Release signature cryptography is also covered by existing release verifier tests.
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.run import github_update_watch as watch
from sofia.run import systemd_update_watch as unit


REV_A = "a" * 40
REV_B = "b" * 40


def _result(output, code=0):
    return SimpleNamespace(stdout=output, returncode=code)


def test_main_revision_uses_exact_https_ref_and_no_pull():
    observed = []
    def runner(command, **kwargs):
        observed.append((command, kwargs))
        return _result(f"{REV_A}\trefs/heads/main\n")
    assert watch.git_main_revision(runner=runner) == REV_A
    command, arguments = observed[0]
    assert command == [
        "git", "-c", "credential.helper=", "ls-remote", "--exit-code",
        watch.REPOSITORY, watch.BRANCH_REF,
    ]
    assert arguments["timeout"] == 30
    assert arguments["env"]["GIT_TERMINAL_PROMPT"] == "0"


@pytest.mark.parametrize("output", [
    "", "bogus\trefs/heads/main\n",
    f"{REV_A}\trefs/heads/development\n",
    f"{REV_A}\trefs/heads/main\n{REV_B}\trefs/heads/main\n",
])
def test_invalid_remote_revision_is_never_eligible(output):
    with pytest.raises(watch.UpdateWatchError):
        watch.git_main_revision(runner=lambda *a, **kw: _result(output))


def test_remote_failure_does_not_become_no_update():
    with pytest.raises(watch.UpdateWatchError):
        watch.git_main_revision(runner=lambda *a, **kw: _result("", 128))


def test_unverified_push_never_requests_install_or_restart(tmp_path):
    observed = watch.inspect_updates(
        installed_revision=REV_A, inbox=tmp_path / "missing",
        head_reader=lambda: REV_B, now=datetime(2026, 10, 11, tzinfo=timezone.utc),
    )
    data = observed.as_json()
    assert observed.status == "awaiting_signed_release"
    assert data["verified_release"] is None
    assert data["activated"] is False
    assert data["runtime_restarted"] is False
    assert data["installed_revision"] == REV_A
    path = tmp_path / "status.json"
    watch.publish_observation(observed, path=path)
    assert '"status":"awaiting_signed_release"' in path.read_text()
    assert path.stat().st_mode & 0o077 == 0


def test_no_false_release_when_head_matches_installed(tmp_path):
    observed = watch.inspect_updates(
        installed_revision=REV_B, inbox=tmp_path,
        head_reader=lambda: REV_B,
    )
    assert observed.status == "up_to_date"
    assert observed.verified_release is None


def test_signed_exact_main_bundle_is_eligible_but_not_activated(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    bundle = inbox / "release-1"
    bundle.mkdir(parents=True)
    (bundle / "signer-key-id.txt").write_text("production-key", encoding="utf-8")
    (bundle / "release-signature.bin").write_bytes(b"signed")
    key = tmp_path / "trusted-public.pem"
    key.write_bytes(b"test public key")
    import sofia.run.github_update_watch as mod
    monkeypatch.setattr(mod, "verify_release_evidence", lambda path:
        SimpleNamespace(git_revision=REV_B, release_id="release-1",
                        manifest_sha256="c" * 64))
    class Verifier:
        def __init__(self, keyring):
            assert keyring == {"production-key": key}
        def verify(self, **kwargs):
            assert kwargs["signature"] == b"signed"
            return True
    monkeypatch.setattr(mod, "Ed25519ReleaseSignatureVerifier", Verifier)
    result = watch.inspect_updates(
        installed_revision=REV_A, inbox=inbox,
        public_key=key, signer_key_id="production-key",
        head_reader=lambda: REV_B,
    )
    assert result.status == "signed_release_available"
    assert result.verified_release.release_id == "release-1"
    assert result.as_json()["activated"] is False


def test_signature_rejection_blocks_inbox_promotion(tmp_path, monkeypatch):
    inbox = tmp_path / "inbox"
    bundle = inbox / "signed-looking"
    bundle.mkdir(parents=True)
    (bundle / "signer-key-id.txt").write_text("prod")
    (bundle / "release-signature.bin").write_bytes(b"wrong signature")
    key = tmp_path / "pub.pem"
    key.write_text("not actually a key")
    monkeypatch.setattr(watch, "verify_release_evidence", lambda path:
        SimpleNamespace(git_revision=REV_A, release_id="candidate",
                        manifest_sha256="d" * 64))
    class DenySignature:
        def __init__(self, _):
            pass
        def verify(self, **_):
            return False
    monkeypatch.setattr(watch, "Ed25519ReleaseSignatureVerifier", DenySignature)
    assert watch.verified_inbox_release(
        inbox=inbox, upstream_revision=REV_A,
        public_key=key, signer_key_id="prod",
    ) is None


def test_installed_revision_receipt_rejects_symlinks(tmp_path):
    actual = tmp_path / "head"
    actual.write_text(REV_A)
    symlink = tmp_path / "alias"
    symlink.symlink_to(actual)
    with pytest.raises(watch.UpdateWatchError):
        watch.installed_revision_from_file(symlink)


def test_systemd_watcher_is_isolated_and_never_requests_restart():
    rendered = unit.render_service()
    assert "DynamicUser=yes" in rendered
    assert "StateDirectory=sofia-updater" in rendered
    assert "NoNewPrivileges=true" in rendered
    assert "ProtectSystem=strict" in rendered
    assert "sofia.run.github_update_watch" in rendered
    assert "systemctl restart" not in rendered
    assert "sofia-runtime.service" not in [
        line for line in rendered.splitlines() if line.startswith("Exec")
    ]
    assert "OnUnitActiveSec=15min" in unit.render_timer()


@pytest.mark.parametrize("bad", ["/tmp/a path", "../../escape", "/tmp/../escape"])
def test_watcher_unit_rejects_unsafe_runtime_executable(bad):
    with pytest.raises(ValueError):
        unit.render_service(python_path=bad)


def test_watcher_unit_requires_paired_signing_config():
    with pytest.raises(ValueError):
        unit.render_service(trusted_key_file="/etc/sofia/key.pem")
