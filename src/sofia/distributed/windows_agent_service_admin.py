"""Install/update/remove/validate the Windows Fleet-agent service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import subprocess
import sys

from sofia.distributed.agent_main import configuration_from_file
from sofia.distributed.windows_agent_service import (
    SERVICE_DESCRIPTION,
    SERVICE_DISPLAY_NAME,
    SERVICE_NAME,
    SofiaFleetAgentWindowsService,
)


CLASS_STRING = (
    "sofia.distributed.windows_agent_service."
    "SofiaFleetAgentWindowsService"
)


@dataclass(frozen=True, slots=True)
class FleetAgentServiceStatus:
    installed: bool
    state: str
    config_path: str | None
    class_string: str | None
    valid: bool
    detail: str


def _require_windows():
    if sys.platform != "win32":
        raise RuntimeError(
            "Fleet agent service administration requires Windows"
        )
    import win32service
    import win32serviceutil
    return win32service, win32serviceutil


def _configure_recovery() -> None:
    for argv in (
        (
            "sc.exe",
            "failure",
            SERVICE_NAME,
            "reset=",
            "86400",
            "actions=",
            "restart/5000/restart/15000/restart/60000",
        ),
        ("sc.exe", "failureflag", SERVICE_NAME, "1"),
    ):
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
            )
            raise RuntimeError(
                "failed to configure Fleet-agent service recovery: "
                + detail
            )


def _python_class_string() -> str | None:
    import winreg

    key_path = (
        rf"SYSTEM\CurrentControlSet\Services\"
        rf"{SERVICE_NAME}\PythonClass"
    )
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            key_path,
        ) as key:
            return winreg.QueryValue(key, None)
    except FileNotFoundError:
        return None


def install_or_update(config_path: Path) -> None:
    if not isinstance(config_path, Path) or not config_path.is_file():
        raise FileNotFoundError(
            "existing Fleet agent config file required"
        )
    configuration_from_file(config_path)
    win32service, util = _require_windows()
    kwargs = dict(
        startType=win32service.SERVICE_AUTO_START,
        description=SERVICE_DESCRIPTION,
        delayedstart=True,
    )
    try:
        util.InstallService(
            CLASS_STRING,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            **kwargs,
        )
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1073:
            raise
        util.ChangeServiceConfig(
            CLASS_STRING,
            SERVICE_NAME,
            displayName=SERVICE_DISPLAY_NAME,
            **kwargs,
        )
    util.SetServiceCustomOption(
        SERVICE_NAME,
        "ConfigPath",
        str(config_path.resolve()),
    )
    _configure_recovery()


def remove() -> None:
    _, util = _require_windows()
    try:
        util.StopService(SERVICE_NAME)
    except Exception:
        pass
    try:
        util.RemoveService(SERVICE_NAME)
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1060:
            raise


def start() -> None:
    _, util = _require_windows()
    util.StartService(SERVICE_NAME)


def stop() -> None:
    _, util = _require_windows()
    util.StopService(SERVICE_NAME)


def status(
    *,
    expected_config_path: Path | None = None,
) -> FleetAgentServiceStatus:
    win32service, util = _require_windows()
    try:
        raw = util.QueryServiceStatus(SERVICE_NAME)
    except Exception as exc:
        if getattr(exc, "winerror", None) == 1060:
            return FleetAgentServiceStatus(
                installed=False,
                state="missing",
                config_path=None,
                class_string=None,
                valid=False,
                detail="service is not installed",
            )
        raise

    labels = {
        win32service.SERVICE_STOPPED: "stopped",
        win32service.SERVICE_START_PENDING: "start_pending",
        win32service.SERVICE_STOP_PENDING: "stop_pending",
        win32service.SERVICE_RUNNING: "running",
        win32service.SERVICE_CONTINUE_PENDING: "continue_pending",
        win32service.SERVICE_PAUSE_PENDING: "pause_pending",
        win32service.SERVICE_PAUSED: "paused",
    }
    state = labels.get(raw[1], f"state:{raw[1]}")
    config_path = util.GetServiceCustomOption(
        SERVICE_NAME,
        "ConfigPath",
        None,
    )
    class_string = _python_class_string()
    valid = (
        bool(config_path)
        and class_string == CLASS_STRING
    )
    details: list[str] = []
    if class_string != CLASS_STRING:
        valid = False
        details.append("PythonClass mismatch")
    if not config_path:
        valid = False
        details.append("ConfigPath missing")
    if expected_config_path is not None:
        expected = str(expected_config_path.resolve())
        if config_path != expected:
            valid = False
            details.append("ConfigPath mismatch")
    return FleetAgentServiceStatus(
        installed=True,
        state=state,
        config_path=config_path,
        class_string=class_string,
        valid=valid,
        detail=(
            "; ".join(details)
            or "registration matches expected Fleet-agent contract"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog=(
            "python -m "
            "sofia.distributed.windows_agent_service_admin"
        )
    )
    parser.add_argument(
        "action",
        choices=("install", "start", "stop", "validate", "remove"),
    )
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    config_path = Path(args.config) if args.config else None

    try:
        if args.action == "install":
            if config_path is None:
                raise ValueError("--config is required for install")
            install_or_update(config_path)
            return 0
        if args.action == "start":
            start()
            return 0
        if args.action == "stop":
            stop()
            return 0
        if args.action == "remove":
            remove()
            return 0
        result = status(expected_config_path=config_path)
        print(
            f"{SERVICE_NAME}: installed={result.installed}; "
            f"state={result.state}; valid={result.valid}; "
            f"{result.detail}"
        )
        return 0 if result.valid else 2
    except Exception as exc:
        print(
            "Fleet agent service administration failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
