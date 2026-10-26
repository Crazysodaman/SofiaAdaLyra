"""Per-user GUI launchers for the generic Platform client.

Installation is an explicit operator command.  It never starts Core, changes
machine-wide services, embeds credentials, or requires administrator access.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Mapping

from sofia.platform.state.atomic_file import atomic_write_text


_APPLICATIONS = {
    "desktop": ("Sofía Desktop", "Open the selected companion Core desktop"),
    "tray": ("Sofía Tray", "Open companion connection status and controls"),
    "settings": ("Sofía Settings", "Edit authorized companion settings"),
    "control-center": (
        "Sofía Platform Control Center", "Inspect companion Platform status",
    ),
}


@dataclass(frozen=True, slots=True)
class UILauncherInstallOptions:
    tray_autostart: bool = False
    desktop_autostart: bool = False
    desktop_shortcuts: bool = False

    def __post_init__(self) -> None:
        for field in ("tray_autostart", "desktop_autostart", "desktop_shortcuts"):
            if type(getattr(self, field)) is not bool:
                raise TypeError(f"{field} must be boolean")


@dataclass(frozen=True, slots=True)
class UILauncherInstallReceipt:
    platform: str
    installed: tuple[str, ...]
    autostart: tuple[str, ...]


def _python_gui_executable(executable: Path) -> Path:
    if sys.platform == "win32":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.is_file():
            return pythonw
    return executable


def launcher_argv(command: str, *, executable: Path | None = None) -> tuple[str, ...]:
    if command not in _APPLICATIONS:
        raise ValueError("unsupported UI launcher command")
    runner = _python_gui_executable(Path(executable or sys.executable).resolve())
    return (str(runner), "-m", "sofia.platform.launcher", command)


def _safe_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir():
        raise PermissionError(f"launcher directory is unsafe: {path}")


def _write_desktop_file(path: Path, command: str, *, executable: Path) -> None:
    if path.exists() and (path.is_symlink() or not path.is_file()):
        raise PermissionError(f"launcher target is unsafe: {path}")
    name, comment = _APPLICATIONS[command]
    argv = launcher_argv(command, executable=executable)
    def quote(value: str) -> str:
        # XDG Exec is not a POSIX shell. Use its double-quoted argument rules
        # and escape characters with special meaning inside double quotes.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        escaped = escaped.replace("`", "\\`").replace("$", "\\$")
        return f'"{escaped}"'

    rendered = " ".join(quote(value) for value in argv)
    atomic_write_text(path, (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Comment={comment}\n"
        f"Exec={rendered}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=true\n"
    ))
    path.chmod(0o644)


def install_xdg_launchers(
    options: UILauncherInstallOptions, *, environment: Mapping[str, str] | None = None,
    executable: Path | None = None,
) -> UILauncherInstallReceipt:
    if not isinstance(options, UILauncherInstallOptions):
        raise TypeError("UILauncherInstallOptions required")
    env = dict(os.environ if environment is None else environment)
    home_raw = env.get("HOME", "").strip()
    if not home_raw:
        raise RuntimeError("HOME is required for per-user XDG launchers")
    home = Path(home_raw).resolve()
    data = Path(env.get("XDG_DATA_HOME", str(home / ".local/share"))).resolve()
    config = Path(env.get("XDG_CONFIG_HOME", str(home / ".config"))).resolve()
    applications = data / "applications"
    autostart = config / "autostart"
    _safe_directory(applications)
    _safe_directory(autostart)
    runner = Path(executable or sys.executable)
    installed = []
    for command in _APPLICATIONS:
        target = applications / f"companion-runtime-{command}.desktop"
        _write_desktop_file(target, command, executable=runner)
        installed.append(str(target))
    auto = []
    requested = {
        "tray": options.tray_autostart,
        "desktop": options.desktop_autostart,
    }
    for command, enabled in requested.items():
        target = autostart / f"companion-runtime-{command}.desktop"
        if enabled:
            _write_desktop_file(target, command, executable=runner)
            auto.append(str(target))
        elif target.exists():
            if target.is_symlink() or not target.is_file():
                raise PermissionError(f"autostart target is unsafe: {target}")
            target.unlink()
    return UILauncherInstallReceipt("linux-xdg", tuple(installed), tuple(auto))


_POWERSHELL_SHORTCUT = r"""
$ErrorActionPreference='Stop'
$shell=New-Object -ComObject WScript.Shell
$link=$shell.CreateShortcut($args[0])
$link.TargetPath=$args[1]
$link.Arguments=$args[2]
$link.Description=$args[3]
$link.WorkingDirectory=$args[4]
$link.Save()
""".strip()


def install_windows_launchers(
    options: UILauncherInstallOptions, *, environment: Mapping[str, str] | None = None,
    executable: Path | None = None, run=subprocess.run,
    powershell_path: str | None = None, configure_startup=None,
) -> UILauncherInstallReceipt:
    if not isinstance(options, UILauncherInstallOptions):
        raise TypeError("UILauncherInstallOptions required")
    env = dict(os.environ if environment is None else environment)
    appdata = env.get("APPDATA", "").strip()
    userprofile = env.get("USERPROFILE", "").strip()
    if not appdata or not userprofile:
        raise RuntimeError("APPDATA and USERPROFILE are required")
    start = Path(appdata).resolve() / "Microsoft/Windows/Start Menu/Programs/Sofía"
    desktop = Path(userprofile).resolve() / "Desktop"
    _safe_directory(start)
    if options.desktop_shortcuts:
        _safe_directory(desktop)
    powershell = (
        powershell_path or shutil.which("powershell.exe")
        or shutil.which("powershell")
    )
    if powershell is None:
        raise RuntimeError("PowerShell is required to create Windows shortcuts")
    runner = Path(executable or sys.executable)
    installed = []
    for command, (name, description) in _APPLICATIONS.items():
        argv = launcher_argv(command, executable=runner)
        arguments = subprocess.list2cmdline(argv[1:])
        targets = [start / f"{name}.lnk"]
        if options.desktop_shortcuts:
            targets.append(desktop / f"{name}.lnk")
        for target in targets:
            if target.exists() and target.is_symlink():
                raise PermissionError("Windows shortcut target cannot be a symlink")
            run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command",
                 _POWERSHELL_SHORTCUT, str(target), argv[0], arguments,
                 description, str(Path(argv[0]).parent)],
                check=True, capture_output=True, text=True,
            )
            installed.append(str(target))
    if configure_startup is None:
        from sofia.modules.ui.windows_startup import configure_windows_ui_startup
        configure_startup = configure_windows_ui_startup
    configure_startup(
        tray_enabled=options.tray_autostart,
        desktop_enabled=options.desktop_autostart,
        executable=runner,
    )
    auto = tuple(
        command for command, enabled in (
            ("tray", options.tray_autostart),
            ("desktop", options.desktop_autostart),
        ) if enabled
    )
    return UILauncherInstallReceipt("windows", tuple(installed), auto)


def install_user_launchers(
    options: UILauncherInstallOptions, *, platform: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> UILauncherInstallReceipt:
    selected = platform or sys.platform
    if selected == "win32":
        return install_windows_launchers(options, environment=environment)
    if selected.startswith("linux"):
        return install_xdg_launchers(options, environment=environment)
    raise RuntimeError(f"per-user UI launcher installation is unsupported on {selected}")
