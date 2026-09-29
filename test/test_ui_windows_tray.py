import importlib
from queue import Queue
import sys

import pytest

from sofia.ui.control_center import GameMode, TrayCommand, TrayStatus
from sofia.ui.windows_tray import WindowsTrayAgent, WindowsTrayUnavailable


def _status():
    return TrayStatus(
        runtime_host="venus",
        runtime_state="running",
        llm_host="venus",
        llm_state="running",
        llm_model="vendor/primary:9b",
        game_mode=GameMode.AUTO,
        fleet_total=3,
        fleet_healthy=3,
        fleet_attention=0,
        llm_secondary_model="vendor/open:4b",
        cognitive_routing_enabled=True,
    )


def test_windows_tray_module_import_is_safe_without_initializing_win32():
    sys.modules.pop("sofia.ui.windows_tray",None)
    module=importlib.import_module("sofia.ui.windows_tray")
    assert hasattr(module,"WindowsTrayAgent")


def test_non_windows_start_fails_cleanly(monkeypatch):
    monkeypatch.setattr(sys,"platform","linux")
    agent=WindowsTrayAgent(events=Queue(),status_provider=_status)
    with pytest.raises(WindowsTrayUnavailable,match="Windows"):
        agent.start()


def test_tray_agent_requires_typed_command_queue():
    queue=Queue()
    agent=WindowsTrayAgent(events=queue,status_provider=_status)
    queue.put(TrayCommand.OPEN_CHAT)
    assert queue.get() is TrayCommand.OPEN_CHAT


def test_default_tray_icon_is_bundled_fox():
    agent = WindowsTrayAgent(events=Queue(), status_provider=_status)
    assert agent.icon_path.name == "sofia_fox.ico"
    assert agent.icon_path.is_file()
