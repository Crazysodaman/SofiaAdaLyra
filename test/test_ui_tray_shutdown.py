from contextlib import AbstractContextManager
from pathlib import Path
from types import SimpleNamespace

import sofia.ui.tray_agent as tray_agent


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
    monkeypatch.setattr(tray_agent, "TrayAgentApplication", lambda: app)
    monkeypatch.setattr(tray_agent, "TrayProcessLock", lambda path: _Lock())

    assert tray_agent.main() == 0
