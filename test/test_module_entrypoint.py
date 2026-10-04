import runpy
import sys

import pytest


def test_module_entrypoint_launches_desktop_by_default(monkeypatch):
    calls: list[str] = []
    configuration = object()

    def run_desktop(configuration=None):
        assert configuration is expected_configuration
        calls.append("desktop")
        return 0

    def ensure_tray(received_configuration):
        assert received_configuration is expected_configuration
        calls.append("tray")
        return True

    expected_configuration = configuration

    monkeypatch.setattr(sys, "argv", ["sofia"])
    monkeypatch.setattr(
        "sofia.config.create_production_configuration",
        lambda: configuration,
    )
    monkeypatch.setattr(
        "sofia.ui.desktop.run_desktop",
        run_desktop,
    )
    monkeypatch.setattr(
        "sofia.ui.tray_launcher.ensure_tray_agent",
        ensure_tray,
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(
            "src/sofia/__main__.py",
            run_name="__main__",
        )

    assert exc_info.value.code == 0
    assert calls == ["tray", "desktop"]


def test_module_entrypoint_cli_preserves_terminal_client(monkeypatch):
    calls: list[str] = []

    class FakeConfiguration:
        pass

    configuration = FakeConfiguration()

    class FakeApplication:
        def __init__(self, received_configuration):
            calls.append("application")
            assert received_configuration is configuration

    class FakeConversationLoop:
        def __init__(
            self,
            application,
            input_function=input,
            output_function=print,
        ):
            calls.append("conversation")
            assert isinstance(application, FakeApplication)

        def run(self):
            calls.append("run")

    monkeypatch.setattr(sys, "argv", ["sofia", "--cli"])
    monkeypatch.setattr(
        "sofia.config.create_production_configuration",
        lambda: configuration,
    )
    monkeypatch.setattr(
        "sofia.application.SofiaApplication",
        FakeApplication,
    )
    monkeypatch.setattr(
        "sofia.ui.terminal.ConversationLoop",
        FakeConversationLoop,
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(
            "src/sofia/__main__.py",
            run_name="__main__",
        )

    assert exc_info.value.code == 0
    assert calls == ["application", "conversation", "run"]


def test_module_entrypoint_rejects_unknown_argument(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["sofia", "--wat"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(
            "src/sofia/__main__.py",
            run_name="__main__",
        )

    assert exc_info.value.code == 2
    assert "Usage: python -m sofia" in capsys.readouterr().out
