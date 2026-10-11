"""Headless canonical application service: source contracts, not host deployment."""
from pathlib import Path, PurePosixPath
from threading import Event
from types import SimpleNamespace

import pytest

from sofia.run import systemd_runtime as runtime


def spec() -> runtime.SystemdRuntimeSpec:
    return runtime.SystemdRuntimeSpec(
        python_path=PurePosixPath("/opt/sofia/.venv/bin/python"),
        state_root=PurePosixPath("/var/lib/sofia-ada-lyra"),
        environment_file=PurePosixPath("/etc/sofia/production.env"),
        service_user="sofia",
    )


def test_approved_debian_13_runtime_has_separate_os_preflight_and_canonical_service():
    unit = runtime.render_unit(spec())
    assert "ExecStartPre=/opt/sofia/.venv/bin/python -m sofia.run.systemd_runtime verify-guest" in unit
    assert "ExecStart=/opt/sofia/.venv/bin/python -m sofia.run.systemd_runtime" in unit
    assert "ExecStart=" not in unit.replace(
        "ExecStart=/opt/sofia/.venv/bin/python -m sofia.run.systemd_runtime", ""
    )
    assert "EnvironmentFile=/etc/sofia/production.env" in unit
    assert "SOFIA_RUNTIME_MODE=production" in unit
    assert "SOFIA_IDENTITY_BOOTSTRAP_MODE=require_existing" in unit
    assert "ConditionPathExists=/var/lib/sofia-ada-lyra/sofia.db" in unit
    assert "ReadWritePaths=/var/lib/sofia-ada-lyra" in unit
    assert "User=sofia\nGroup=sofia\n" in unit
    assert "Type=notify" in unit
    assert "NotifyAccess=main" in unit
    assert "TimeoutStartSec=180s" in unit
    assert "Restart=on-failure" in unit
    assert "KillSignal=SIGTERM" in unit
    assert "ProtectSystem=strict" in unit
    assert "NoNewPrivileges=true" in unit
    assert "ProtectHome=true" in unit
    assert "WantedBy=multi-user.target" in unit
    assert "install " not in unit and "systemctl enable" not in unit


@pytest.mark.parametrize("unsafe", [
    PurePosixPath("relative/python"),
    PurePosixPath("/tmp/../python"),
    PurePosixPath("/tmp/with space/python"),
    PurePosixPath("/tmp/%n/python"),
    PurePosixPath("/"),
])
def test_unit_spec_rejects_unsafe_executable_paths(unsafe):
    with pytest.raises(ValueError, match="safe absolute"):
        runtime.SystemdRuntimeSpec(
            python_path=unsafe,
            state_root=spec().state_root,
            environment_file=spec().environment_file,
        )


@pytest.mark.parametrize("account", ["root", "nobody", "a b", "foo;bar", ""])
def test_service_must_not_run_as_root_or_untrusted_account(account):
    with pytest.raises(ValueError, match="dedicated unprivileged"):
        runtime.SystemdRuntimeSpec(
            python_path=spec().python_path,
            state_root=spec().state_root,
            environment_file=spec().environment_file,
            service_user=account,
        )


def test_runtime_refuses_missing_signed_pointer_without_opening_any_db(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    monkeypatch.delenv("SOFIA_STATE_HOME_POINTER", raising=False)
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    with pytest.raises(PermissionError, match="signed state-home pointer"):
        runtime.run_headless(stop_event=Event())
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mode,identity", [
    ("development", "require_existing"),
    ("production", "first_bootstrap"),
])
def test_runtime_rejects_environment_file_overrides_before_state_bootstrap(
    monkeypatch, mode, identity,
):
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", mode)
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", identity)
    monkeypatch.setenv("SOFIA_STATE_HOME_POINTER", "/etc/sofia/home-pointer.json")
    with pytest.raises(PermissionError, match="production and require_existing"):
        runtime.run_headless(stop_event=Event())


def test_runtime_uses_existing_application_and_always_shuts_down(
    tmp_path, monkeypatch,
):
    from sofia.application import bootstrap
    from sofia.config import defaults

    state = tmp_path / "sofia.db"
    state.touch()
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    monkeypatch.setenv("SOFIA_STATE_HOME_POINTER", "/etc/sofia/home-pointer.json")
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    monkeypatch.setattr(defaults, "production_state_path", lambda: state)
    monkeypatch.setattr(
        defaults, "create_production_configuration",
        lambda: SimpleNamespace(state_path=state),
    )
    actions = []
    monkeypatch.setattr(
        runtime, "require_existing_sqlite",
        lambda path: actions.append(("state_checked", path)),
    )
    stop = Event()

    class Application:
        def __init__(self, config):
            actions.append(("composed", config.state_path))

        def start(self):
            actions.append(("started", state))
            stop.set()

        def shutdown(self):
            actions.append(("shutdown", state))

    monkeypatch.setattr(bootstrap, "SofiaApplication", Application)
    monkeypatch.setattr(runtime, "require_debian_guest", lambda: None)
    monkeypatch.setattr(runtime, "notify_systemd", lambda message: actions.append(("notify", message)))
    runtime.run_headless(stop_event=stop)
    assert actions == [
        ("state_checked", state),
        ("composed", state),
        ("started", state),
        ("notify", "READY=1"),
        ("notify", "STOPPING=1"),
        ("shutdown", state),
    ]


def test_headless_entrypoint_can_render_unit_without_host_side_effects(capsys):
    result = runtime.main([
        "render-unit",
        "--python", "/opt/sofia/.venv/bin/python",
        "--state-root", "/var/lib/sofia-ada-lyra",
        "--environment-file", "/etc/sofia/production.env",
    ])
    out = capsys.readouterr().out
    assert result == 0
    assert "[Service]" in out
    assert "systemctl " not in out


def test_debian_13_trixie_guest_is_accepted_without_starting_service(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    release = tmp_path / "os-release"
    release.write_text(
        'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\\n'
        'ID=debian\\nVERSION_ID="13"\\nVERSION_CODENAME=trixie\\n',
        encoding="utf-8",
    )
    runtime.require_debian_guest(os_release_path=release)


@pytest.mark.parametrize("contents", [
    'ID=arch\\nBUILD_ID=rolling\\n',
    'ID=ubuntu\\nID_LIKE=debian\\nVERSION_ID="24.04"\\n',
    'ID=debian\\nVERSION_ID="12"\\nVERSION_CODENAME=bookworm\\n',
    'ID=debian\\nVERSION_ID="14"\\nVERSION_CODENAME=forky\\n',
    'ID=debian\\nVERSION_ID="13"\\nVERSION_CODENAME=bookworm\\n',
    'ID=debian\\n',
])
def test_debian_guest_rejects_unapproved_distros_and_major_versions(
    tmp_path, monkeypatch, contents,
):
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    release = tmp_path / "os-release"
    release.write_text(contents, encoding="utf-8")
    with pytest.raises(RuntimeError, match="requires reviewed Debian 13"):
        runtime.require_debian_guest(os_release_path=release)


def test_debian_guest_refuses_missing_release_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(FileNotFoundError):
        runtime.require_debian_guest(os_release_path=tmp_path / "not-provisioned")


def test_unit_guest_preflight_is_read_only_and_does_not_start_canonical_runtime(
    monkeypatch,
):
    seen = []
    monkeypatch.setattr(runtime, "require_debian_guest", lambda: seen.append("guest"))
    assert runtime.main(["verify-guest"]) == 0
    assert seen == ["guest"]


def test_debian_service_refuses_no_systemd_notify_socket_before_state_access(
    monkeypatch,
):
    from types import SimpleNamespace
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    monkeypatch.setenv("SOFIA_STATE_HOME_POINTER", "/etc/sofia/home-pointer.json")
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    with pytest.raises(RuntimeError, match="readiness notification channel"):
        runtime.run_headless(stop_event=Event())


def test_fixed_systemd_notifications_use_unix_socket_without_shell(monkeypatch):
    messages = []
    connections = []
    class Datagram:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def connect(self, addr):
            connections.append(addr)
        def sendall(self, payload):
            messages.append(payload)
    monkeypatch.setenv("NOTIFY_SOCKET", "@sofia-control")
    monkeypatch.setattr(runtime.socket, "socket", lambda family, socktype: Datagram())
    runtime.notify_systemd("READY=1")
    runtime.notify_systemd("STOPPING=1")
    assert connections == ["\\0sofia-control", "\\0sofia-control"]
    assert messages == [b"READY=1", b"STOPPING=1"]
    with pytest.raises(ValueError, match="fixed lifecycle"):
        runtime.notify_systemd("READY=1\\nMAINPID=1")
