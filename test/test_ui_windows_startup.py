import sys

import pytest

from sofia.ui import windows_startup
from sofia.ui.windows_startup import (
    WindowsStartupUnavailable,
    configure_windows_startup,
    tray_startup_command,
)


def test_startup_command_bootstraps_tray_from_package_root(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"
    monkeypatch.setattr(sys, "executable", str(executable))
    command = tray_startup_command()
    assert "sofia.ui.tray_agent import main" in command
    assert "sys.path.insert(0" in command
    assert repr(str(windows_startup._package_root())) in command
    assert " -c " in command
    assert "pythonw.exe" in command.casefold() or "python.exe" in command.casefold()


def test_package_root_contains_sofia_package():
    assert (windows_startup._package_root() / "sofia").is_dir()


def test_non_windows_registration_fails_without_touching_registry(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(WindowsStartupUnavailable):
        configure_windows_startup(True)


def test_startup_command_prefers_available_windowless_python(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"
    windowless = tmp_path / "pythonw.exe"
    windowless.touch()
    monkeypatch.setattr(sys, "executable", str(executable))
    command = tray_startup_command()
    assert command.startswith(windows_startup.subprocess.list2cmdline((str(windowless),)))
    assert "sofia.ui.tray_agent import main" in command
