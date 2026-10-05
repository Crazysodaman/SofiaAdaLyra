from contextlib import AbstractContextManager
from pathlib import Path
from types import SimpleNamespace

import sofia.ui.tray_agent as tray_agent
from sofia.ui.process_lock import TrayProcessAlreadyRunning


class _InterruptingApplication:
    def __init__(self, state_path: Path) -> None:
        self.config = SimpleNamespace(state_path=state_path)

    def run(self) -> int:
        raise KeyboardInterrupt


class _Lock(AbstractContextManager):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_main_treats_keyboard_interrupt_as_clean_shutdown(tmp_path, monkeypatch):
    app = _InterruptingApplication(tmp_path / "sofia.db")
    monkeypatch.setattr(tray_agent, "TrayAgentApplication", lambda **kwargs: app)
    monkeypatch.setattr(tray_agent, "TrayProcessLock", lambda path: _Lock())

    assert tray_agent.main([]) == 0


def test_main_reports_duplicate_tray_without_traceback(tmp_path, monkeypatch, capsys):
    app = SimpleNamespace(config=SimpleNamespace(state_path=tmp_path / "sofia.db"))
    monkeypatch.setattr(tray_agent, "TrayAgentApplication", lambda **kwargs: app)

    class _DuplicateLock:
        def __enter__(self):
            raise TrayProcessAlreadyRunning("already owned")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(tray_agent, "TrayProcessLock", lambda path: _DuplicateLock())

    assert tray_agent.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "Sofía tray agent is already running."
