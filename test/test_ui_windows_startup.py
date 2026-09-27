from pathlib import Path
import sys

import pytest

from sofia.ui.windows_startup import (
    WindowsStartupUnavailable,
    configure_windows_startup,
    tray_startup_command,
)


def test_startup_command_launches_tray_module_with_current_python():
    command=tray_startup_command()
    assert "-m sofia.ui.tray_agent" in command
    assert command.startswith('"')


def test_non_windows_registration_fails_without_touching_registry(monkeypatch):
    monkeypatch.setattr(sys,"platform","linux")
    with pytest.raises(WindowsStartupUnavailable):
        configure_windows_startup(True)
