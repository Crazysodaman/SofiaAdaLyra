from sofia.ui.control_center import (
    ServiceAction,
    ServiceKind,
    TrayCommand,
)
from sofia.ui.tray_agent import TrayAgentApplication


def test_exit_ui_stops_only_tray_loop_not_runtime_service():
    app = object.__new__(TrayAgentApplication)
    calls = []
    app._service_action = (
        lambda kind, action, **kwargs: calls.append(
            (kind, action, kwargs)
        )
    )

    keep_running = app.handle(TrayCommand.EXIT_UI)

    assert keep_running is False
    assert calls == []


def test_runtime_stop_remains_a_distinct_explicit_tray_command():
    app = object.__new__(TrayAgentApplication)
    calls = []
    app._last_error = None
    app._service_action = (
        lambda kind, action, **kwargs: calls.append(
            (kind, action, kwargs)
        )
    )

    keep_running = app.handle(TrayCommand.RUNTIME_STOP)

    assert keep_running is True
    assert calls == [
        (
            ServiceKind.SOFIA_RUNTIME,
            ServiceAction.STOP,
            {},
        )
    ]
from threading import Event, Lock


def test_slow_model_control_runs_off_the_tray_event_thread():
    app = object.__new__(TrayAgentApplication)
    app._model_control_lock = Lock()
    app._model_control_active = False
    app._last_error = None
    app._cognition_runtime_state = type("State", (), {
        "snapshot": lambda self: None,
    })()
    started = Event()
    release = Event()
    finished = Event()
    app._refresh_model_runtime_state = lambda: finished.set()

    def operation():
        started.set()
        assert release.wait(timeout=5)

    app._queue_model_control(operation)

    assert started.wait(timeout=1)
    assert app._model_control_active is True
    release.set()
    assert finished.wait(timeout=1)
