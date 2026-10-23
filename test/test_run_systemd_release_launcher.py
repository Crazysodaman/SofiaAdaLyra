"""Debian signed-release launcher and privileged environment admission.

No VM/systemd process, canonical database or host update is started in tests.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from sofia.platform.run import systemd_release_launcher as launcher
from sofia.platform.run.active_release import ReleaseEnvironmentManager


def _stub_state(monkeypatch, active):
    seen = []
    monkeypatch.setattr(launcher, "require_existing_sqlite",
                        lambda p: seen.append(("existing", p)))
    class Resolver:
        def __init__(self, *, state_path):
            seen.append(("resolver", state_path))
        def resolve(self):
            return active
    monkeypatch.setattr(launcher, "ActiveReleaseResolver", Resolver)
    return seen


def test_no_signed_release_uses_explicit_bootstrap_without_creating_new_state(
    tmp_path, monkeypatch,
):
    seen = _stub_state(monkeypatch, None)
    db = tmp_path / "sofia.db"
    bootstrap = tmp_path / "bootstrap-python"
    assert launcher.interpreter_for_active_release(
        state_path=db, bootstrap_python=bootstrap,
    ) == bootstrap
    assert seen == [("existing", db), ("resolver", db)]
    assert not db.exists()


def test_trusted_prepared_release_is_selected_read_only(tmp_path, monkeypatch):
    release = SimpleNamespace(
        release_id="release-1", manifest_sha256="a" * 64,
        artifact_sha256="b" * 64, application_version="0.1.0",
    )
    _stub_state(monkeypatch, release)
    home = tmp_path / "environments"
    target = home / "release-1"
    (target / "bin").mkdir(parents=True)
    (target / "bin" / "python").write_bytes(b"test interpreter")
    monkeypatch.setattr(launcher.os, "access", lambda *_args: True)
    (target / ".sofia-release.json").write_text(
        json.dumps(ReleaseEnvironmentManager._stamp(release))
    )
    observed = []
    monkeypatch.setattr(launcher, "_privileged_read_only_dir",
                        lambda p: observed.append(p))
    selected = launcher.interpreter_for_active_release(
        state_path=tmp_path / "sofia.db",
        release_environments=home,
    )
    assert selected == target / "bin" / "python"
    assert observed == [home, target]


def test_tampered_version_stamp_denies_deployment(tmp_path, monkeypatch):
    release = SimpleNamespace(
        release_id="release-1", manifest_sha256="a" * 64,
        artifact_sha256="b" * 64, application_version="0.1.0",
    )
    _stub_state(monkeypatch, release)
    home = tmp_path / "environments"
    target = home / release.release_id
    (target / "bin").mkdir(parents=True)
    (target / "bin" / "python").write_bytes(b"test interpreter")
    monkeypatch.setattr(launcher.os, "access", lambda *_args: True)
    (target / ".sofia-release.json").write_text(
        json.dumps({"release_id": "release-1", "manifest_sha256": "wrong"})
    )
    monkeypatch.setattr(launcher, "_privileged_read_only_dir", lambda p: None)
    with pytest.raises(launcher.DebianReleaseLauncherError, match="does not match"):
        launcher.interpreter_for_active_release(
            state_path=tmp_path / "sofia.db", release_environments=home,
        )


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX ownership/mode")
def test_unprivileged_release_tree_is_rejected(tmp_path):
    home = tmp_path / "environments"
    home.mkdir(mode=0o777)
    home.chmod(0o777)
    with pytest.raises(launcher.DebianReleaseLauncherError):
        launcher._privileged_read_only_dir(home)


def test_release_path_cannot_escape_environment_root(tmp_path, monkeypatch):
    release = SimpleNamespace(release_id="../escape")
    _stub_state(monkeypatch, release)
    home = tmp_path / "environments"
    home.mkdir()
    monkeypatch.setattr(launcher, "_privileged_read_only_dir", lambda _: None)
    with pytest.raises(launcher.DebianReleaseLauncherError, match="escaped"):
        launcher.interpreter_for_active_release(
            state_path=tmp_path / "sofia.db", release_environments=home,
        )


def test_launcher_refuses_unauthorized_canonical_environment(monkeypatch, capsys):
    monkeypatch.setattr(launcher, "require_debian_guest", lambda: None)
    monkeypatch.delenv("SOFIA_STATE_HOME_POINTER", raising=False)
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    monkeypatch.setattr(launcher.os, "execve",
                        lambda *_args: pytest.fail("must not exec"))
    assert launcher.main() == 2
    assert "approved canonical" in capsys.readouterr().err
