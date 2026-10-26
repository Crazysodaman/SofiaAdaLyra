"""Per-user Windows startup registration for the Sofía tray client."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "SofiaAdaLyraTray"
_DESKTOP_VALUE_NAME = "SofiaAdaLyraDesktop"


class WindowsStartupUnavailable(RuntimeError):
    pass


def _python_gui_executable(executable: Path) -> Path:
    pythonw = executable.with_name("pythonw.exe")
    return pythonw if pythonw.is_file() else executable


def _package_root() -> Path:
    """Return the directory that contains the top-level sofia package."""

    # ``windows_startup.py`` lives at ``sofia/modules/ui`` in both an editable
    # source tree and an installed wheel.  The import root is therefore the
    # parent of the top-level ``sofia`` package, not the package directory
    # itself.
    return Path(__file__).resolve().parents[3]


def tray_startup_command(*, state_path: Path | None = None) -> str:
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    runner = pythonw if pythonw.is_file() else executable
    package_root = _package_root()
    code = "import sys; " + f"sys.path.insert(0, {str(package_root)!r}); "
    if state_path is not None:
        code += f"sys.argv = ['sofia-tray', '--state-path', {str(state_path.resolve())!r}]; "
    code += "from sofia.modules.ui.tray_agent import main; raise SystemExit(main())"
    return subprocess.list2cmdline((str(runner), "-c", code))


def configure_windows_startup(enabled: bool, *, state_path: Path | None = None) -> None:
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
                tray_startup_command(state_path=state_path),
            )
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
            except FileNotFoundError:
                pass


def configure_windows_ui_startup(
    *, tray_enabled: bool, desktop_enabled: bool,
    executable: Path | None = None,
) -> None:
    """Configure independent generic clients for the current Windows user."""
    if type(tray_enabled) is not bool or type(desktop_enabled) is not bool:
        raise TypeError("startup choices must be boolean")
    if sys.platform != "win32":
        raise WindowsStartupUnavailable("Windows startup registration requires Windows")
    import winreg

    runner = _python_gui_executable(Path(executable or sys.executable))
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE,
    ) as key:
        for name, enabled, command in (
            (_VALUE_NAME, tray_enabled, "tray"),
            (_DESKTOP_VALUE_NAME, desktop_enabled, "desktop"),
        ):
            if enabled:
                value = subprocess.list2cmdline((
                    str(runner), "-m", "sofia.platform.launcher", command,
                ))
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            else:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
