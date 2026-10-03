"""systemd service packaging for Sofía's Fleet agent on Linux."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import os
import shlex
import subprocess
import sys

SERVICE_NAME = "sofia-fleet-agent.service"


@dataclass(frozen=True, slots=True)
class SystemdFleetAgentSpec:
    python_path: Path
    config_path: Path
    state_directory: Path
    service_user: str = "sofia-fleet"

    def __post_init__(self) -> None:
        if not isinstance(self.python_path, Path) or not self.python_path.is_absolute():
            raise ValueError("python_path must be an absolute Path")
        if not isinstance(self.config_path, Path) or not self.config_path.is_absolute():
            raise ValueError("config_path must be an absolute Path")
        if not isinstance(self.state_directory, Path) or not self.state_directory.is_absolute():
            raise ValueError("state_directory must be an absolute Path")
        if (
            not isinstance(self.service_user, str)
            or not self.service_user.strip()
            or any(ch.isspace() for ch in self.service_user)
        ):
            raise ValueError("service_user must be a nonempty account name")


def _systemd_escape_arg(value: Path) -> str:
    # systemd ExecStart uses its own quoting rules; shlex.quote safely preserves
    # whitespace and metacharacters for the simple argv we emit.
    return shlex.quote(str(value))


def render_unit(spec: SystemdFleetAgentSpec) -> str:
    if not isinstance(spec, SystemdFleetAgentSpec):
        raise TypeError("spec must be SystemdFleetAgentSpec")
    python_path = _systemd_escape_arg(spec.python_path)
    config_path = _systemd_escape_arg(spec.config_path)
    state_directory = str(spec.state_directory)

    return f"""[Unit]
Description=Sofía Ada Lyra Fleet Agent
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={spec.service_user}
Group={spec.service_user}
ExecStart={python_path} -m sofia.distributed.agent_main --config {config_path}
Restart=on-failure
RestartSec=5s
TimeoutStopSec=30s
KillSignal=SIGTERM
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
MemoryDenyWriteExecute=true
ReadWritePaths={state_directory}

[Install]
WantedBy=multi-user.target
"""


def _run(argv: list[str]) -> None:
    completed = subprocess.run(
        argv,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"command failed ({completed.returncode}): "
            f"{' '.join(argv)}: {detail}"
        )


def install_unit(
    spec: SystemdFleetAgentSpec,
    *,
    unit_path: Path = Path("/etc/systemd/system") / SERVICE_NAME,
    enable_now: bool = True,
) -> None:
    if sys.platform == "win32":
        raise RuntimeError("systemd Fleet service is unavailable on Windows")
    if os.geteuid() != 0:
        raise PermissionError("systemd service installation requires root")
    if not spec.python_path.is_file():
        raise FileNotFoundError("Fleet agent Python executable does not exist")
    if not spec.config_path.is_file():
        raise FileNotFoundError("Fleet agent config does not exist")
    spec.state_directory.mkdir(parents=True, exist_ok=True)

    unit_path.write_text(render_unit(spec), encoding="utf-8")
    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", SERVICE_NAME])
    if enable_now:
        _run(["systemctl", "restart", SERVICE_NAME])


def remove_unit(
    *,
    unit_path: Path = Path("/etc/systemd/system") / SERVICE_NAME,
) -> None:
    if sys.platform == "win32":
        raise RuntimeError("systemd Fleet service is unavailable on Windows")
    if os.geteuid() != 0:
        raise PermissionError("systemd service removal requires root")
    subprocess.run(
        ["systemctl", "disable", "--now", SERVICE_NAME],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    try:
        unit_path.unlink()
    except FileNotFoundError:
        pass
    _run(["systemctl", "daemon-reload"])


def service_active() -> bool:
    if sys.platform == "win32":
        return False
    completed = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE_NAME],
        check=False,
        timeout=15,
    )
    return completed.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.distributed.systemd_agent_service"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    install = sub.add_parser("install")
    install.add_argument("--python", required=True)
    install.add_argument("--config", required=True)
    install.add_argument("--state-dir", required=True)
    install.add_argument("--user", default="sofia-fleet")
    install.add_argument("--no-start", action="store_true")

    sub.add_parser("remove")
    sub.add_parser("status")

    args = parser.parse_args(argv)
    try:
        if args.action == "install":
            install_unit(
                SystemdFleetAgentSpec(
                    python_path=Path(args.python).resolve(),
                    config_path=Path(args.config).resolve(),
                    state_directory=Path(args.state_dir).resolve(),
                    service_user=args.user,
                ),
                enable_now=not args.no_start,
            )
            return 0
        if args.action == "remove":
            remove_unit()
            return 0
        active = service_active()
        print(
            f"{SERVICE_NAME}: active={active}"
        )
        return 0 if active else 2
    except Exception as exc:
        print(
            f"systemd Fleet service failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
