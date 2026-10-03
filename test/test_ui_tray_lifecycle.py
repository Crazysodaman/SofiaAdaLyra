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
