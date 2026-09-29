import runpy
import sys

import pytest


def test_module_entrypoint_launches_desktop_by_default(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(sys, "argv", ["sofia"])
    monkeypatch.setattr(
        "sofia.ui.desktop.run_desktop",
        lambda configuration=None: calls.append("desktop") or 0,
    )
    monkeypatch.setattr(
        "sofia.ui.tray_launcher.ensure_tray_agent",
        lambda configuration: calls.append("tray") or True,
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
        "sofia.application.ConversationLoop",
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
