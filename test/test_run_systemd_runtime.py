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


def test_debian_and_arch_share_one_real_systemd_application_unit():
    unit = runtime.render_unit(spec())
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
    runtime.run_headless(stop_event=stop)
    assert actions == [
        ("state_checked", state),
        ("composed", state),
        ("started", state),
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
