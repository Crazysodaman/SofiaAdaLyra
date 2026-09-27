"""Per-user Windows startup registration for the Sofía tray client."""
from __future__ import annotations

from pathlib import Path
import sys


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "SofiaAdaLyraTray"


class WindowsStartupUnavailable(RuntimeError):
    pass


def tray_startup_command() -> str:
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    runner = pythonw if pythonw.is_file() else executable
    return f'"{runner}" -m sofia.ui.tray_agent'


def configure_windows_startup(enabled: bool) -> None:
    if not isinstance(enabled, bool):
        raise TypeError("enabled must be boolean")
    if sys.platform != "win32":
        raise WindowsStartupUnavailable("Windows startup registration requires Windows")
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        _RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                _VALUE_NAME,
                0,
                winreg.REG_SZ,
                tray_startup_command(),
            )
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
            except FileNotFoundError:
                pass
