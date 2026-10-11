"""Headless canonical Sofía application under Debian 13 systemd.

This is the *application* runtime, not the independently enrolled Fleet agent.
An operator-provided signed state-home pointer is mandatory. This module does
not create a state home, move a writer, mint migration authority or enable a
service on any host. An external privileged broker must fence the prior writer.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import os
import re
import signal
import socket
import sys
from threading import Event

from sofia.state.canonical_sqlite import require_existing_sqlite

SERVICE_NAME = "sofia-runtime.service"
DEBIAN_VERSION_ID = "13"
DEBIAN_CODENAME = "trixie"
_USER = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/+@-]+$")


@dataclass(frozen=True, slots=True)
class SystemdRuntimeSpec:
    """Operator-reviewed guest-local paths, not auto-discovered host grants."""

    python_path: PurePosixPath
    state_root: PurePosixPath
    environment_file: PurePosixPath
    service_user: str = "sofia"

    def __post_init__(self) -> None:
        for label in ("python_path", "state_root", "environment_file"):
            value = getattr(self, label)
            if (
                not isinstance(value, PurePosixPath)
                or not value.is_absolute()
                or str(value) == "/"
                or ".." in value.parts
                or _SAFE_PATH.fullmatch(str(value)) is None
            ):
                raise ValueError(
                    f"{label} must be a safe absolute POSIX path without escapes"
                )
        if (
            not isinstance(self.service_user, str)
            or not _USER.fullmatch(self.service_user)
            or self.service_user in {"root", "nobody"}
        ):
            raise ValueError("service_user must be a dedicated unprivileged account name")


def require_debian_guest(*, os_release_path: Path = Path("/etc/os-release")) -> None:
    """Refuse an unreviewed OS before starting a new canonical state writer.

    The operator selected Debian 13 Stable. A later Debian major upgrade
    requires an explicit source/config review rather than silent promotion.
    This is a local OS compatibility check, *not* migration authorization.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("canonical headless runtime requires Linux")
    raw = os_release_path.read_text(encoding="utf-8")
    if len(raw) > 32768:
        raise ValueError("guest os-release is unexpectedly large")
    values: dict[str, str] = {}
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "VERSION_ID", "VERSION_CODENAME"}:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            values[key] = value
    if (
        values.get("ID") != "debian"
        or values.get("VERSION_ID") != DEBIAN_VERSION_ID
        or values.get("VERSION_CODENAME", DEBIAN_CODENAME) != DEBIAN_CODENAME
    ):
        raise RuntimeError(
            "canonical Sofia VM requires reviewed Debian 13 (trixie) guest; "
            "refusing unapproved distribution or major upgrade"
        )


def render_unit(spec: SystemdRuntimeSpec) -> str:
    """Render a real headless application unit; never enable or install it."""
    if not isinstance(spec, SystemdRuntimeSpec):
        raise TypeError("SystemdRuntimeSpec required")
    return f"""[Unit]
Description=Sofía Ada Lyra canonical headless runtime (Debian 13)
Wants=network-online.target
After=network-online.target
# Do not start against a missing or unmounted canonical database.
ConditionPathExists={spec.state_root}/sofia.db

[Service]
Type=notify
NotifyAccess=main
TimeoutStartSec=180s
User={spec.service_user}
Group={spec.service_user}
Environment=SOFIA_RUNTIME_MODE=production
Environment=SOFIA_IDENTITY_BOOTSTRAP_MODE=require_existing
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile={spec.environment_file}
ExecStartPre={spec.python_path} -m sofia.run.systemd_runtime verify-guest
ExecStart={spec.python_path} -m sofia.run.systemd_runtime
Restart=on-failure
RestartSec=10s
TimeoutStopSec=60s
KillSignal=SIGTERM
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
PrivateDevices=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
ReadWritePaths={spec.state_root}

[Install]
WantedBy=multi-user.target
"""


def notify_systemd(message: str) -> None:
    """Notify systemd via inherited AF_UNIX datagram; never claim ready early."""
    if message not in {"READY=1", "STOPPING=1"}:
        raise ValueError("only fixed lifecycle notifications are supported")
    address = os.environ.get("NOTIFY_SOCKET", "")
    if not address or len(address) > 100:
        raise RuntimeError("canonical runtime requires systemd NOTIFY_SOCKET")
    # systemd uses @name to represent an abstract Linux UNIX socket.
    destination = ("\\0" + address[1:]) if address.startswith("@") else address
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
        connection.connect(destination)
        connection.sendall(message.encode("ascii"))


def run_headless(*, stop_event: Event) -> None:
    """Start the actual canonical application and shut it down on signal.

    The signed pointer is consumed by existing production configuration, and
    the existing state guard prevents a silently new/symlinked database.
    Runtime enrollment, remote GPU cognition and service APIs remain owned by
    the normal production SofiaApplication composition.
    """
    if not sys.platform.startswith("linux"):
        raise RuntimeError("headless systemd runtime requires Linux")
    if not isinstance(stop_event, Event):
        raise TypeError("stop_event must be a threading.Event")
    # EnvironmentFile settings can override systemd Environment entries.
    # Reject that explicitly rather than permitting first-bootstrap mode or
    # an untrusted runtime mode on the future sole-writer VM.
    if (
        os.environ.get("SOFIA_RUNTIME_MODE") != "production"
        or os.environ.get("SOFIA_IDENTITY_BOOTSTRAP_MODE") != "require_existing"
    ):
        raise PermissionError(
            "canonical headless service requires production and "
            "require_existing identity modes"
        )
    if not os.environ.get("NOTIFY_SOCKET", "").strip():
        raise RuntimeError("canonical systemd service requires readiness notification channel")
    if not os.environ.get("SOFIA_STATE_HOME_POINTER", "").strip():
        raise PermissionError(
            "headless production runtime requires operator-approved signed "
            "state-home pointer; refusing implicit local writer"
        )
    require_debian_guest()
    from sofia.config.defaults import (
        create_production_configuration,
        production_state_path,
    )
    from sofia.application.bootstrap import SofiaApplication

    state_path = production_state_path()
    require_existing_sqlite(state_path)
    configuration = create_production_configuration()
    if Path(configuration.state_path) != Path(state_path):
        raise PermissionError("canonical runtime state pointer/configuration mismatch")
    if stop_event.is_set():
        return
    application = SofiaApplication(configuration)
    try:
        application.start()
        notify_systemd("READY=1")
        stop_event.wait()
    finally:
        try:
            notify_systemd("STOPPING=1")
        finally:
            application.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.run.systemd_runtime",
    )
    sub = parser.add_subparsers(dest="command")
    show = sub.add_parser("render-unit", help="Print a unit for operator review only")
    show.add_argument("--python", required=True)
    show.add_argument("--state-root", required=True)
    show.add_argument("--environment-file", required=True)
    show.add_argument("--user", default="sofia")
    sub.add_parser("verify-guest", help="Verify approved Debian 13 OS only; no services start")
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-guest":
            require_debian_guest()
            return 0
        if args.command == "render-unit":
            print(render_unit(SystemdRuntimeSpec(
                python_path=PurePosixPath(args.python),
                state_root=PurePosixPath(args.state_root),
                environment_file=PurePosixPath(args.environment_file),
                service_user=args.user,
            )), end="")
            return 0
        stopper = Event()

        def stop(_signum: int, _frame: object) -> None:
            stopper.set()

        previous_term = signal.signal(signal.SIGTERM, stop)
        previous_int = signal.signal(signal.SIGINT, stop)
        try:
            run_headless(stop_event=stopper)
        finally:
            signal.signal(signal.SIGTERM, previous_term)
            signal.signal(signal.SIGINT, previous_int)
        return 0
    except (OSError, RuntimeError, TypeError, ValueError, PermissionError) as exc:
        print(
            f"canonical headless runtime refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
