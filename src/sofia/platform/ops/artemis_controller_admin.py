"""Operator-facing SCM installation for the independent Artemis controller.

Unlike the existing Fleet agent, this host service is deliberately separate,
MANUAL-start until live host acceptance and cannot be installed as LocalSystem.
No password is accepted on argv and no broad VM management is granted here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import socket
import sys

from sofia.platform.ops.artemis_controller import ArtemisControllerConfig
from sofia.platform.ops.artemis_controller_service import (
    SERVICE_DESCRIPTION, SERVICE_DISPLAY_NAME, SERVICE_NAME,
)

CLASS_STRING = "sofia.platform.ops.artemis_controller_service.SofiaArtemisControllerService"
# The initial read-only controller supports LocalService or an independently
# configured group-managed identity. A local password-bearing service account
# would require an interactive SCM provisioning process, never CLI secrets.
LOCAL_SERVICE = "NT AUTHORITY\\LocalService"


@dataclass(frozen=True, slots=True)
class ControllerServiceStatus:
    installed: bool
    state: str
    class_string: str | None
    config_path: str | None
    service_identity: str | None
    valid: bool
    detail: str


def require_artemis_windows() -> None:
    if sys.platform != "win32" or socket.gethostname().casefold().split(".")[0] != "artemis":
        raise RuntimeError("Artemis controller service administration requires Artemis Windows host")


def permitted_service_account(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("service account required; LocalSystem forbidden")
    account = value.strip()
    if account.casefold() == LOCAL_SERVICE.casefold():
        return LOCAL_SERVICE
    # Domain-managed service accounts can be provisioned by the operator.
    # No arbitrary hostname, admin account, or password is accepted.
    if (
        "\\" in account
        and account.endswith("$")
        and not any(ch.isspace() for ch in account)
        and 3 <= len(account) <= 128
        and account.split("\\", 1)[0].casefold() not in {"nt authority", ".", "artemis"}
        and len(account.split("\\", 1)) == 2
        and all(part for part in account.split("\\", 1))
    ):
        return account
    raise ValueError("controller service requires explicit LocalService or provisioned domain gMSA")


def _win32():
    require_artemis_windows()
    import win32service
    import win32serviceutil
    return win32service, win32serviceutil


def _python_class_string() -> str | None:
    import winreg
    key_path = (
        "SYSTEM\\CurrentControlSet\\Services\\"
        + SERVICE_NAME + "\\PythonClass"
    )
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            return winreg.QueryValue(key, None)
    except FileNotFoundError:
        return None


def _configured_account(win32service) -> str:
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        handle = win32service.OpenService(
            scm, SERVICE_NAME, win32service.SERVICE_QUERY_CONFIG
        )
        try:
            settings = win32service.QueryServiceConfig(handle)
            return str(settings[7])
        finally:
            win32service.CloseServiceHandle(handle)
    finally:
        win32service.CloseServiceHandle(scm)


def install(*, config_path: Path, service_account: str) -> None:
    win32service, util = _win32()
    account = permitted_service_account(service_account)
    config = ArtemisControllerConfig.load(config_path)
    if not config.audit_directory.is_dir():
        raise FileNotFoundError("preprovisioned host-local journal directory required")
    # Refuse overwrite: change requests must be supervised and never silently
    # upgrade an already installed, privileged SCM registration.
    if status().installed:
        raise RuntimeError("controller already installed; validate and review before changing")
    util.InstallService(
        CLASS_STRING,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        startType=win32service.SERVICE_DEMAND_START,
        userName=account,
        password=None,
        description=SERVICE_DESCRIPTION,
    )
    util.SetServiceCustomOption(
        SERVICE_NAME, "ConfigPath", str(config_path.resolve())
    )
    # No automatic start, no forced restart and no Hyper-V write grants.


def status(*, expected_config: Path | None = None) -> ControllerServiceStatus:
    win32service, util = _win32()
    try:
        raw = util.QueryServiceStatus(SERVICE_NAME)
    except Exception as exc:
        if getattr(exc, "winerror", None) == 1060:
            return ControllerServiceStatus(
                False, "missing", None, None, None, False, "not installed"
            )
        raise
    states = {
        win32service.SERVICE_RUNNING: "running",
        win32service.SERVICE_STOPPED: "stopped",
        win32service.SERVICE_START_PENDING: "starting",
        win32service.SERVICE_STOP_PENDING: "stopping",
    }
    state = states.get(raw[1], "other")
    cls = _python_class_string()
    cfg = util.GetServiceCustomOption(SERVICE_NAME, "ConfigPath", None)
    user = _configured_account(win32service)
    try:
        permitted_service_account(user)
        account_ok = True
    except ValueError:
        account_ok = False
    path_ok = bool(cfg)
    if expected_config is not None:
        path_ok = path_ok and cfg == str(expected_config.resolve())
    valid = cls == CLASS_STRING and path_ok and account_ok
    return ControllerServiceStatus(
        True, state, cls, cfg, user, valid,
        "registration and restricted service identity verified" if valid
        else "controller class, config path or service account mismatch",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Artemis-only independent controller SCM administration")
    parser.add_argument("action", choices=("install", "validate", "start", "stop"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--service-account", help="LocalService or separately provisioned domain gMSA")
    args = parser.parse_args(argv)
    try:
        require_artemis_windows()
        if args.action == "install":
            if args.config is None or args.service_account is None:
                raise ValueError("install requires --config and --service-account")
            install(config_path=args.config, service_account=args.service_account)
            print("Artemis controller installed in manual-start mode only")
        elif args.action == "validate":
            report = status(expected_config=args.config)
            print(report)
            return 0 if report.valid else 2
        else:
            report = status(expected_config=args.config)
            if not report.valid:
                raise RuntimeError("cannot start/stop unverified SCM registration")
            _, util = _win32()
            if args.action == "start":
                util.StartService(SERVICE_NAME)
            else:
                util.StopService(SERVICE_NAME)
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"Artemis controller administration refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
