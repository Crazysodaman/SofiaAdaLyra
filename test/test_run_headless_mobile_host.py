"""Regression contracts for authenticated client hosting on the headless owner.

These are isolated source tests: no socket, VM, credential or service is
provisioned. Live PKI, reconnect and guest acceptance require a separate run.
"""
from pathlib import Path
from queue import Queue
from threading import Event, Thread, get_ident
from types import SimpleNamespace

import pytest

from sofia.run import systemd_runtime as runtime


def test_mobile_http_proxy_dispatches_only_on_headless_application_thread():
    commands = Queue()
    stop = Event()
    owner_thread = get_ident()
    observed = []
    output = []

    class Gateway:
        def dispatch_authenticated(self, *, credential, operation, payload):
            observed.append((get_ident(), credential, operation, payload))
            stop.set()
            return {"accepted": True, "id": payload["request_id"]}

    def caller():
        output.append(
            runtime._HeadlessMobileDispatch(commands).dispatch_authenticated(
                credential="owner-device-credential",
                operation="/v1/mobile/chat",
                payload={"request_id": "desktop:12345678"},
            )
        )

    worker = Thread(target=caller, daemon=True)
    worker.start()
    runtime._process_mobile_commands(
        commands=commands, gateway=Gateway(), stop_event=stop,
    )
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert output == [{"accepted": True, "id": "desktop:12345678"}]
    assert observed == [
        (owner_thread, "owner-device-credential", "/v1/mobile/chat",
         {"request_id": "desktop:12345678"})
    ]


def _prepare_runtime(tmp_path: Path, monkeypatch):
    from sofia.application import bootstrap
    from sofia.config import defaults

    state = tmp_path / "sofia.db"
    state.touch()
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "production")
    monkeypatch.setenv("SOFIA_IDENTITY_BOOTSTRAP_MODE", "require_existing")
    monkeypatch.setenv("SOFIA_STATE_HOME_POINTER", "/etc/sofia/home-pointer.json")
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    monkeypatch.setattr(runtime, "require_debian_guest", lambda: None)
    monkeypatch.setattr(runtime, "require_existing_sqlite", lambda _path: None)
    monkeypatch.setattr(defaults, "production_state_path", lambda: state)
    monkeypatch.setattr(
        defaults, "create_production_configuration",
        lambda: SimpleNamespace(state_path=state),
    )
    actions = []
    stopped = Event()

    class FakeApplication:
        def __init__(self, config):
            actions.append("constructed")
            self.config = config

        def start(self):
            actions.append("application_started")

        def shutdown(self):
            actions.append("application_stopped")

    monkeypatch.setattr(bootstrap, "SofiaApplication", FakeApplication)

    def notify(message):
        actions.append(message)
        if message == "READY=1":
            stopped.set()

    monkeypatch.setattr(runtime, "notify_systemd", notify)
    return state, stopped, actions


def test_debian_mobile_endpoint_starts_after_canonical_application_and_stops_first(
    tmp_path, monkeypatch,
):
    from sofia.mobile import gateway, provisioning, server

    state, stopped, actions = _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        provisioning.MobileProvisioning, "from_runtime",
        lambda _config: SimpleNamespace(enabled=True, server=object()),
    )

    class FakeGateway:
        def __init__(self, application, *, state_path):
            assert application.config.state_path == state
            assert state_path == state
            actions.append("gateway_bound")
            self.credentials = object()

    class FakeServer:
        def __init__(self, gateway, *, credentials, configuration):
            assert isinstance(gateway, runtime._HeadlessMobileDispatch)
            actions.append("server_bound")
        def start(self):
            actions.append("server_started")
        def close(self):
            actions.append("server_stopped")

    monkeypatch.setattr(gateway, "MobileCompanionGateway", FakeGateway)
    monkeypatch.setattr(server, "MobileCompanionServer", FakeServer)
    runtime.run_headless(stop_event=stopped)
    assert actions == [
        "constructed", "application_started", "gateway_bound",
        "server_bound", "server_started", "READY=1", "server_stopped",
        "STOPPING=1", "application_stopped",
    ]


def test_failing_authenticated_endpoint_refuses_ready_and_stops_canonical_app(
    tmp_path, monkeypatch,
):
    from sofia.mobile import gateway, provisioning, server

    _, stopped, actions = _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(
        provisioning.MobileProvisioning, "from_runtime",
        lambda _config: SimpleNamespace(enabled=True, server=object()),
    )

    class FakeGateway:
        def __init__(self, application, *, state_path):
            self.credentials = object()

    class FakeServer:
        def __init__(self, gateway, *, credentials, configuration):
            pass
        def start(self):
            raise OSError("TLS binding failure")
        def close(self):
            actions.append("server_closed")

    monkeypatch.setattr(gateway, "MobileCompanionGateway", FakeGateway)
    monkeypatch.setattr(server, "MobileCompanionServer", FakeServer)
    with pytest.raises(OSError, match="TLS binding failure"):
        runtime.run_headless(stop_event=stopped)
    assert "READY=1" not in actions
    assert actions[-3:] == [
        "server_closed", "STOPPING=1", "application_stopped",
    ]
