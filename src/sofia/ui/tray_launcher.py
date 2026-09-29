"""Production launcher for the singleton Windows tray agent."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import time

from sofia.config.model import SofiaConfiguration
from sofia.ui.process_lock import TrayProcessAlreadyRunning, TrayProcessLock


def _pythonw() -> Path:
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return candidate if candidate.is_file() else executable


def tray_agent_is_running(configuration: SofiaConfiguration) -> bool:
    """Return True when another live process owns this state database tray."""
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be SofiaConfiguration")
    lock = TrayProcessLock(configuration.state_path)
    try:
        lock.acquire()
    except TrayProcessAlreadyRunning:
        return True
    else:
        lock.release()
        return False


def ensure_tray_agent(configuration: SofiaConfiguration) -> bool:
    """Ensure the Windows tray singleton is alive.

    Returns True when this call launched a new tray process and False when the
    tray was already running or the current platform is not Windows.
    """
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError("configuration must be SofiaConfiguration")
    if sys.platform != "win32":
        return False
    if tray_agent_is_running(configuration):
        return False

    creationflags = (
        getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    process = subprocess.Popen(
        (str(_pythonw()), "-m", "sofia.ui.tray_agent"),
        cwd=str(Path(__file__).resolve().parents[3]),
        creationflags=creationflags,
        close_fds=True,
    )

    # Catch immediate import/configuration failures without turning tray launch
    # into a long blocking startup path.
    time.sleep(0.15)
    code = process.poll()
    if code is not None and code != 0:
        raise RuntimeError(
            f"Sofía tray agent exited during startup with code {code}"
        )
    return True
