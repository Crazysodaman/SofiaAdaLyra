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
from queue import Empty, Queue

from sofia.platform.state.canonical_sqlite import require_existing_sqlite
from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration

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
    roles: PlatformRoleConfiguration = PlatformRoleConfiguration((
        PlatformRole.CORE_HOST,
        PlatformRole.MODULE_HOST,
    ))

    def __post_init__(self) -> None:
        if not isinstance(self.roles, PlatformRoleConfiguration):
            raise TypeError("roles must be PlatformRoleConfiguration")
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
        self.roles.require(PlatformRole.CORE_HOST)


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
        or values.get("VERSION_CODENAME") != DEBIAN_CODENAME
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
Environment=SOFIA_PLATFORM_ROLES={','.join(role.value for role in spec.roles.roles)}
Environment=PYTHONDONTWRITEBYTECODE=1
EnvironmentFile={spec.environment_file}
ExecStartPre={spec.python_path} -m sofia.platform.run.systemd_runtime verify-guest
# Stable launcher performs read-only signed-release interpreter selection.
# The actual canonical application still owns this same systemd service PID.
ExecStart={spec.python_path} -m sofia.platform.run.systemd_release_launcher
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



class _HeadlessMobileDispatch:
    """Marshal authenticated client operations onto the canonical application thread.

    Neither the HTTPS request thread nor the Windows desktop becomes an
    application/database writer.  The existing per-device credential is
    independently verified in the HTTP handler AND again by MobileGateway.
    """

    def __init__(self, commands: Queue) -> None:
        self._commands = commands

    def dispatch_authenticated(
        self, *, credential: str, operation: str, payload: dict[str, object],
    ) -> dict[str, object]:
        result: Queue = Queue(maxsize=1)
        try:
            self._commands.put((credential, operation, payload, result), timeout=5)
            succeeded, value = result.get(timeout=130)
        except Empty as exc:
            # An interrupted response may have committed a conversation turn.
            # The caller must use the original stable request ID for status
            # lookup; this boundary never retries or fabricates a completion.
            raise TimeoutError("canonical application dispatch result unknown") from exc
        if succeeded:
            return value
        if isinstance(value, BaseException):
            raise value
        raise RuntimeError("canonical application failed without a result")


def _process_mobile_commands(
    *,
    commands: Queue,
    gateway: object,
    stop_event: Event,
) -> None:
    """Process one queued authenticated call at a time on the runtime owner."""
    while not stop_event.is_set():
        try:
            credential, operation, payload, result = commands.get(timeout=0.25)
        except Empty:
            continue
        try:
            answer = gateway.dispatch_authenticated(
                credential=credential, operation=operation, payload=payload,
            )
        except Exception as exc:
            result.put((False, exc))
        else:
            result.put((True, answer))


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
    PlatformRoleConfiguration.from_environment().require(PlatformRole.CORE_HOST)
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
    from sofia.platform.config.defaults import (
        create_production_configuration,
        production_state_path,
    )
    from sofia.platform.application.bootstrap import SofiaApplication

    state_path = production_state_path()
    require_existing_sqlite(state_path)
    configuration = create_production_configuration()
    if Path(configuration.state_path) != Path(state_path):
        raise PermissionError("canonical runtime state pointer/configuration mismatch")
    if stop_event.is_set():
        return
    application = SofiaApplication(configuration)
    mobile_server = None
    try:
        application.start()
        # A shutdown request can arrive while application.start() is still
        # composing. Never publish READY after a stop was already requested.
        if stop_event.is_set():
            return

        # The authoritative Debian application, not a Windows desktop copy,
        # hosts the existing per-device authenticated mobile endpoint.
        # Keep all gateway/application work on this same service owner thread.
        from sofia.modules.mobile.provisioning import MobileProvisioning
        mobile = MobileProvisioning.from_runtime(configuration)
        mobile_commands: Queue = Queue(maxsize=16)
        mobile_gateway = None
        if mobile.enabled:
            from sofia.modules.mobile.gateway import MobileCompanionGateway
            from sofia.modules.mobile.server import MobileCompanionServer
            mobile_gateway = MobileCompanionGateway(
                application, state_path=configuration.state_path,
            )
            mobile_server = MobileCompanionServer(
                _HeadlessMobileDispatch(mobile_commands),
                credentials=mobile_gateway.credentials,
                configuration=mobile.server,
            )
            mobile_server.start()

        if stop_event.is_set():
            return
        notify_systemd("READY=1")
        if mobile_gateway is None:
            stop_event.wait()
        else:
            _process_mobile_commands(
                commands=mobile_commands,
                gateway=mobile_gateway,
                stop_event=stop_event,
            )
    finally:
        try:
            if mobile_server is not None:
                mobile_server.close()
        finally:
            try:
                notify_systemd("STOPPING=1")
            finally:
                application.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.platform.run.systemd_runtime",
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
