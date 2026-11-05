import importlib
from queue import Queue
import sys

import pytest

from sofia.modules.ui.control_center import GameMode, TrayCommand, TrayStatus
from sofia.modules.ui.windows_tray import WindowsTrayAgent, WindowsTrayUnavailable


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
    sys.modules.pop("sofia.modules.ui.windows_tray",None)
    module=importlib.import_module("sofia.modules.ui.windows_tray")
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


def test_stop_timeout_keeps_live_tray_thread_tracked(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    agent = WindowsTrayAgent(events=Queue(), status_provider=_status)

    class LiveThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            raise AssertionError("a timed-out tray must not be joined as stopped")

    class TimedOutStop:
        def is_set(self):
            return False

        def wait(self, timeout=None):
            assert timeout == 5
            return False

    thread = LiveThread()
    agent._thread = thread
    agent._stopped = TimedOutStop()
    with pytest.raises(WindowsTrayUnavailable, match="did not acknowledge"):
        agent.stop()
    assert agent._thread is thread
    assert agent.running is True


def test_observed_tray_stop_joins_thread_and_retires_handles(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    agent = WindowsTrayAgent(events=Queue(), status_provider=_status)
    joined = []

    class FinishedThread:
        def join(self, timeout=None):
            joined.append(timeout)

        def is_alive(self):
            return False

    agent._thread = FinishedThread()
    agent._hwnd = 77
    agent._wndproc = object()
    agent._stopped.set()
    agent.stop()
    assert joined == [1]
    assert agent._thread is None
    assert agent._hwnd is None
    assert agent._wndproc is None


def test_restart_clears_stale_tray_events_and_startup_error(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    agent = WindowsTrayAgent(events=Queue(), status_provider=_status)
    agent._ready.set()
    agent._stopped.set()
    agent._startup_error = RuntimeError("old failure")
    agent._hwnd = 99
    agent._wndproc = object()

    class FakeThread:
        def __init__(self, *, target, name, daemon):
            assert name == "sofia-windows-tray"
            assert daemon is True

        def start(self):
            assert not agent._ready.is_set()
            assert not agent._stopped.is_set()
            assert agent._startup_error is None
            assert agent._hwnd is None
            assert agent._wndproc is None
            agent._hwnd = 100
            agent._ready.set()

    import sofia.modules.ui.windows_tray as tray_module
    monkeypatch.setattr(tray_module, "Thread", FakeThread)
    agent.start()
    assert agent._hwnd == 100
