"""Owner-session VTube Studio discovery and on-demand process lifecycle.

Only local interactive Windows user hosts run the launcher. We discover Steam
libraries on any mounted drive without recursive filesystem crawling. We use
VTube Studio's officially supported start_without_steam.bat to avoid Steam
account conflicts; NEVER launch via steam:// or Steam.exe.

An existing VTS process belongs to the user, not Sofía. Closing an instance
requires a persisted PID, process creation time, executable path, and session
record from *our own* launch. We send WM_CLOSE, not taskkill or a force kill.
No remote execution, cross-host token copying, DB writes or model activation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import argparse
import json
import os
from pathlib import Path
import re
import socket
import sys
import time

_APP = "VTube Studio"
_APP_EXE = "VTube Studio.exe"
_LAUNCHER = "start_without_steam.bat"
_APPID = "1325860"
_PROCESS_RECORD = "launched_instance.json"
_MAX_DISCOVERY_ROOTS = 256
_VDF_PATH = re.compile(r'^\s*"(?:path|[0-9]+)"\s*"([^"]+)"', re.I | re.M)


class AvatarHostError(RuntimeError):
    """Descriptive, sanitized host lifecycle failure."""


@dataclass(frozen=True)
class OwnedVTS:
    pid: int
    started: float
    exe: str
    session: int
    host: str


def _steam_libraries_from(root: Path) -> list[Path]:
    """Read Steam libraryfolders.vdf; include legacy and modern path syntax."""
    libraries = [root]
    library_file = root / "steamapps" / "libraryfolders.vdf"
    if library_file.is_file() and not library_file.is_symlink():
        try:
            if library_file.stat().st_size > 1024 * 1024:
                return libraries
            raw = library_file.read_text(encoding="utf-8-sig", errors="replace")
            for match in _VDF_PATH.finditer(raw):
                candidate = Path(match.group(1).replace("\\\\", "\\"))
                if candidate.is_absolute():
                    libraries.append(candidate)
        except OSError:
            pass
    return libraries


def _registered_steam_root() -> list[Path]:
    if sys.platform != "win32":
        return []
    try:
        import winreg
        roots = []
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            for label in ("SteamPath", "SteamExe"):
                try:
                    value, _ = winreg.QueryValueEx(key, label)
                except OSError:
                    continue
                if isinstance(value, str) and value.strip():
                    roots.append(Path(value).parent if label == "SteamExe" else Path(value))
        return roots
    except OSError:
        return []


def _windows_drives() -> tuple[str, ...]:
    if sys.platform != "win32":
        return ()
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        get_type = ctypes.windll.kernel32.GetDriveTypeW
        return tuple(
            f"{chr(ord('A') + n)}:"
            for n in range(26)
            if mask & (1 << n) and get_type(f"{chr(ord('A') + n)}:\\") in (2, 3, 4)
        )
    except (OSError, AttributeError):
        return ()


def candidate_roots(*, steam_roots: tuple[Path, ...] | None = None,
                    drive_names: tuple[str, ...] | None = None) -> tuple[Path, ...]:
    """Generate cheap, deterministic paths; never walk an entire drive."""
    if steam_roots is None:
        steam_roots = tuple(_registered_steam_root())
        for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
            directory = os.environ.get(env_name)
            if directory:
                steam_roots += (Path(directory) / "Steam",)
        drive_names = _windows_drives() if drive_names is None else drive_names
        for drive in drive_names:
            for relative in ("Steam", "SteamLibrary", "Games/Steam",
                             "Games/SteamLibrary", "Program Files (x86)/Steam",
                             "Program Files/Steam"):
                steam_roots += (Path(drive + "/") / relative,)
    collected, seen = [], set()
    for steam in steam_roots:
        for lib in _steam_libraries_from(steam):
            for root in (lib / "steamapps" / "common" / _APP,
                         lib if lib.name.casefold() == _APP.casefold() else None):
                if root is None:
                    continue
                key = os.path.normcase(str(root))
                if key not in seen:
                    seen.add(key)
                    collected.append(root)
                if len(collected) >= _MAX_DISCOVERY_ROOTS:
                    return tuple(collected)
    return tuple(collected)


def verified_install_root(root: Path) -> Path | None:
    """Validate the paired official launcher and VTube Studio executable."""
    if not isinstance(root, Path) or not root.is_absolute():
        return None
    try:
        if (root.is_symlink() or not root.is_dir()
            or any((root / name).is_symlink() or not (root / name).is_file()
                   for name in (_LAUNCHER, _APP_EXE))):
            return None
    except OSError:
        return None
    return root


def locate_vtube_studio(*, explicit: Path | None = None,
                        steam_roots: tuple[Path, ...] | None = None,
                        drive_names: tuple[str, ...] | None = None) -> Path:
    """User override wins. Otherwise Steam metadata and known library roots."""
    if explicit is None:
        override = os.environ.get("SOFIA_VTS_INSTALL_DIR", "").strip()
        if override:
            explicit = Path(override)
    if explicit is not None:
        resolved = verified_install_root(explicit)
        if resolved is None:
            raise AvatarHostError("configured VTube Studio directory has no valid standalone launcher")
        return resolved
    for root in candidate_roots(steam_roots=steam_roots, drive_names=drive_names):
        if verified_install_root(root):
            return root
    raise AvatarHostError(
        "VTube Studio not found in Steam libraries. "
        "Pass --install-dir to select its folder on this computer."
    )


def _interactive_windows_session() -> int:
    if sys.platform != "win32":
        raise AvatarHostError("VTube Studio process control requires Windows")
    try:
        import ctypes
        sid = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
        if not ok or sid.value == 0:
            raise AvatarHostError("VTube Studio must run in the signed-in user's desktop session")
        return int(sid.value)
    except (OSError, AttributeError) as exc:
        raise AvatarHostError("cannot verify interactive Windows session") from exc


def _windows_process_session(pid: int) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        session = ctypes.c_ulong()
        if not ctypes.windll.kernel32.ProcessIdToSessionId(
            pid, ctypes.byref(session),
        ):
            return None
        return int(session.value)
    except (OSError, AttributeError):
        return None


def _processes():
    """List only VTube Studio processes in this interactive Windows session."""
    session = _interactive_windows_session()
    try:
        import psutil
    except ImportError as exc:
        raise AvatarHostError(
            "Install the optional vtube-studio dependencies (psutil required)"
        ) from exc
    output = []
    for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
        try:
            info = proc.info
            if (
                str(info.get("name", "")).casefold() == _APP_EXE.casefold()
                and info.get("exe") and info.get("create_time")
                and _windows_process_session(int(info["pid"])) == session
            ):
                output.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return output


def _identity(proc, session: int) -> OwnedVTS:
    info = proc.info
    return OwnedVTS(int(info["pid"]), float(info["create_time"]),
                    str(info["exe"]), session, socket.gethostname())


def _record_file() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local or sys.platform != "win32":
        raise AvatarHostError("interactive Windows LOCALAPPDATA is required")
    return Path(local) / "SofiaAdaLyra" / "Avatar2D" / "VTubeStudio" / _PROCESS_RECORD


def _read_record(path: Path) -> OwnedVTS | None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if set(data) != set(OwnedVTS.__dataclass_fields__):
            return None
        if type(data["pid"]) is not int or type(data["session"]) is not int:
            return None
        if type(data["started"]) not in (int, float):
            return None
        if not all(isinstance(data[name], str) for name in ("exe", "host")):
            return None
        return OwnedVTS(**data)
    except (OSError, ValueError, TypeError):
        return None


def _write_record(path: Path, record: OwnedVTS) -> None:
    if path.is_symlink() or any(part.is_symlink() for part in path.parents):
        raise AvatarHostError("linked process ownership record location forbidden")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".new")
    if temp.exists() or temp.is_symlink():
        raise AvatarHostError("old staging record exists; inspect manually")
    try:
        with temp.open("x", encoding="utf-8") as file:
            json.dump(asdict(record), file)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _matches(record: OwnedVTS, proc, session: int) -> bool:
    try:
        ident = _identity(proc, session)
        return (
            record.pid == ident.pid
            and abs(record.started - ident.started) < 0.01
            and os.path.normcase(record.exe) == os.path.normcase(ident.exe)
            and record.session == session
            and record.host.casefold() == socket.gethostname().casefold()
        )
    except (KeyError, ValueError, TypeError):
        return False


def launch_on_demand(*, install_dir: Path | None = None,
                     process_list=None, startfile=None, sleep=None,
                     ownership_file: Path | None = None,
                     session: int | None = None, wait_iterations: int = 16) -> dict:
    """Start only if VTS is absent, then record precisely the new instance."""
    sid = _interactive_windows_session() if session is None else session
    processes = _processes if process_list is None else process_list
    existing = processes()
    if existing:
        return {
            "result": "reused_existing", "started_by_sofia": False,
            "may_close": False, "count": len(existing),
        }
    root = locate_vtube_studio(explicit=install_dir)
    own_file = _record_file() if ownership_file is None else ownership_file
    launcher = os.startfile if startfile is None else startfile
    pause = time.sleep if sleep is None else sleep
    before = {p.info["pid"] for p in existing}
    # ShellExecute invokes the official BAT without entering Steam.
    launcher(str(root / _LAUNCHER))
    for _ in range(wait_iterations):
        pause(0.5)
        matches = [
            p for p in processes()
            if p.info["pid"] not in before
            and Path(str(p.info["exe"])).parent == root
        ]
        if len(matches) == 1:
            record = _identity(matches[0], sid)
            _write_record(own_file, record)
            return {
                "result": "launched_owned", "started_by_sofia": True,
                "may_close": True, "pid": record.pid,
            }
        if len(matches) > 1:
            return {
                "result": "ambiguous_instance_ownership", "started_by_sofia": True,
                "may_close": False,
            }
    return {
        "result": "launch_not_verified", "started_by_sofia": True,
        "may_close": False,
    }


def request_graceful_close(*, process_list=None, send_close=None,
                           ownership_file: Path | None = None,
                           session: int | None = None) -> dict:
    """Close only positively identified Sofía-owned process, never arbitrary VTS."""
    sid = _interactive_windows_session() if session is None else session
    path = _record_file() if ownership_file is None else ownership_file
    record = _read_record(path)
    if record is None:
        return {"result": "not_owned", "close_sent": False}
    processes = _processes if process_list is None else process_list
    matching = [p for p in processes() if p.info["pid"] == record.pid and _matches(record, p, sid)]
    if len(matching) != 1:
        return {"result": "ownership_expired_or_mismatched", "close_sent": False}
    sender = _post_wm_close if send_close is None else send_close
    count = sender(record.pid)
    if count < 1:
        return {"result": "no_app_window_found", "close_sent": False}
    return {"result": "graceful_close_requested", "close_sent": True, "pid": record.pid}


def _post_wm_close(pid: int) -> int:
    try:
        import win32con
        import win32gui
        import win32process
    except ImportError as exc:
        raise AvatarHostError("pywin32 is required for graceful Windows window close") from exc
    windows = []
    def collect(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and (
            win32process.GetWindowThreadProcessId(hwnd)[1] == pid
        ):
            windows.append(hwnd)
    win32gui.EnumWindows(collect, None)
    for hwnd in windows:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    return len(windows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit local VTube Studio discovery and owner-safe launch/close"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--discover", action="store_true")
    modes.add_argument("--launch", action="store_true")
    modes.add_argument("--close", action="store_true")
    parser.add_argument("--install-dir", type=Path,
                        help="Optional local VTube Studio install directory (any drive)")
    args = parser.parse_args(argv)
    try:
        if args.discover:
            report = {"found": str(locate_vtube_studio(explicit=args.install_dir))}
        elif args.launch:
            report = launch_on_demand(install_dir=args.install_dir)
        else:
            report = request_graceful_close()
        print(json.dumps(report, indent=2))
        return 0
    except (AvatarHostError, OSError, ValueError) as exc:
        parser.exit(2, f"VTube Studio host: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
