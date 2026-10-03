"""Install, update, validate and remove PKG-RUN Windows services.

The runtime and watchdog are separate SCM services. Installation records the
canonical state database path as a service custom option, configures delayed
automatic start, and sets bounded restart recovery through sc.exe.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import subprocess
import sys

from sofia.config.defaults import production_state_path
from sofia.run.windows_service_spec import (
    RUNTIME_SERVICE,
    WATCHDOG_SERVICE,
    WindowsServiceSpec,
    service_specs,
)


@dataclass(frozen=True, slots=True)
class WindowsServiceStatus:
    name: str
    installed: bool
    state: str
    class_string: str | None
    state_path: str | None
    valid: bool
    detail: str = ""


def _require_windows():
    if sys.platform != "win32":
        raise RuntimeError("Windows service administration requires Windows")
    import win32service
    import win32serviceutil
    return win32service, win32serviceutil


def _configure_recovery(name: str) -> None:
    for argv in (
        (
            "sc.exe",
            "failure",
            name,
            "reset=",
            "86400",
            "actions=",
            "restart/5000/restart/15000/restart/60000",
        ),
        ("sc.exe", "failureflag", name, "1"),
    ):
        completed = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if completed.returncode:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(
                f"failed to configure recovery for {name}: {detail}"
            )


def _python_class_string(name: str) -> str | None:
    import winreg

    key_path = rf"SYSTEM\CurrentControlSet\Services\{name}\PythonClass"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            return winreg.QueryValue(key, None)
    except FileNotFoundError:
        return None


def install_or_update_service(
    spec: WindowsServiceSpec,
    *,
    state_path: Path,
    runtime_service_name: str | None = None,
) -> None:
    if not isinstance(spec, WindowsServiceSpec):
        raise TypeError("spec must be WindowsServiceSpec")
    if not isinstance(state_path, Path):
        raise TypeError("state_path must be a Path")
    if not state_path.is_file():
        raise FileNotFoundError("canonical Sofía state database does not exist")

    win32service, win32serviceutil = _require_windows()
    kwargs = dict(
        startType=win32service.SERVICE_AUTO_START,
        description=spec.description,
        delayedstart=spec.delayed_auto_start,
    )

    try:
        win32serviceutil.InstallService(
            spec.class_string,
            spec.name,
            spec.display_name,
            **kwargs,
        )
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1073:
            raise
        win32serviceutil.ChangeServiceConfig(
            spec.class_string,
            spec.name,
            displayName=spec.display_name,
            **kwargs,
        )

    win32serviceutil.SetServiceCustomOption(
        spec.name,
        "StatePath",
        str(state_path.resolve()),
    )
    if runtime_service_name is not None:
        win32serviceutil.SetServiceCustomOption(
            spec.name,
            "RuntimeServiceName",
            runtime_service_name,
        )
    _configure_recovery(spec.name)


def install_services(*, state_path: Path | None = None) -> None:
    target = state_path or production_state_path()
    install_or_update_service(
        RUNTIME_SERVICE,
        state_path=Path(target),
    )
    install_or_update_service(
        WATCHDOG_SERVICE,
        state_path=Path(target),
        runtime_service_name=RUNTIME_SERVICE.name,
    )


def remove_service(spec: WindowsServiceSpec) -> None:
    _, win32serviceutil = _require_windows()
    try:
        win32serviceutil.StopService(spec.name)
    except Exception:
        pass
    win32serviceutil.RemoveService(spec.name)


def remove_services() -> None:
    for spec in reversed(service_specs()):
        try:
            remove_service(spec)
        except Exception as exc:
            if getattr(exc, "winerror", None) not in {1060, None}:
                raise


def _service_state(name: str) -> tuple[bool, str]:
    win32service, win32serviceutil = _require_windows()
    try:
        status = win32serviceutil.QueryServiceStatus(name)
    except Exception as exc:
        if getattr(exc, "winerror", None) == 1060:
            return False, "missing"
        raise
    code = status[1]
    labels = {
        win32service.SERVICE_STOPPED: "stopped",
        win32service.SERVICE_START_PENDING: "start_pending",
        win32service.SERVICE_STOP_PENDING: "stop_pending",
        win32service.SERVICE_RUNNING: "running",
        win32service.SERVICE_CONTINUE_PENDING: "continue_pending",
        win32service.SERVICE_PAUSE_PENDING: "pause_pending",
        win32service.SERVICE_PAUSED: "paused",
    }
    return True, labels.get(code, f"state:{code}")


def service_status(
    spec: WindowsServiceSpec,
    *,
    expected_state_path: Path | None = None,
) -> WindowsServiceStatus:
    installed, state = _service_state(spec.name)
    if not installed:
        return WindowsServiceStatus(
            name=spec.name,
            installed=False,
            state=state,
            class_string=None,
            state_path=None,
            valid=False,
            detail="service is not installed",
        )

    _, win32serviceutil = _require_windows()
    class_string = _python_class_string(spec.name)
    state_path = win32serviceutil.GetServiceCustomOption(
        spec.name,
        "StatePath",
        None,
    )
    expected = (
        None
        if expected_state_path is None
        else str(expected_state_path.resolve())
    )
    valid = class_string == spec.class_string and bool(state_path)
    detail_parts: list[str] = []
    if class_string != spec.class_string:
        valid = False
        detail_parts.append("PythonClass mismatch")
    if expected is not None and state_path != expected:
        valid = False
        detail_parts.append("StatePath mismatch")
    if not state_path:
        valid = False
        detail_parts.append("StatePath missing")

    return WindowsServiceStatus(
        name=spec.name,
        installed=True,
        state=state,
        class_string=class_string,
        state_path=state_path,
        valid=valid,
        detail="; ".join(detail_parts) or "registration matches expected service contract",
    )


def validate_services(*, state_path: Path | None = None) -> tuple[WindowsServiceStatus, ...]:
    target = Path(state_path or production_state_path())
    return tuple(
        service_status(spec, expected_state_path=target)
        for spec in service_specs()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.run.service_admin")
    parser.add_argument("action", choices=("install", "validate", "remove"))
    parser.add_argument("--state-path")
    args = parser.parse_args(argv)
    target = Path(args.state_path) if args.state_path else None

    try:
        if args.action == "install":
            install_services(state_path=target)
            for status in validate_services(state_path=target):
                print(
                    f"{status.name}: state={status.state}; "
                    f"valid={status.valid}; {status.detail}"
                )
            return 0
        if args.action == "validate":
            statuses = validate_services(state_path=target)
            for status in statuses:
                print(
                    f"{status.name}: installed={status.installed}; "
                    f"state={status.state}; valid={status.valid}; {status.detail}"
                )
            return 0 if all(item.valid for item in statuses) else 2
        remove_services()
        return 0
    except Exception as exc:
        print(
            f"RUN service administration failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
