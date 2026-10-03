"""Live Windows acceptance for the canonical runtime and watchdog services."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys
import time

from sofia.config.defaults import production_state_path
from sofia.run import service_admin
from sofia.run.windows_service_spec import RUNTIME_SERVICE, WATCHDOG_SERVICE


@dataclass(frozen=True, slots=True)
class RuntimeServiceAcceptance:
    registration_valid: bool
    runtime_running: bool
    watchdog_running: bool
    recovery_exercised: bool
    recovery_succeeded: bool

    @property
    def accepted(self) -> bool:
        return (
            self.registration_valid
            and self.runtime_running
            and self.watchdog_running
            and (
                not self.recovery_exercised
                or self.recovery_succeeded
            )
        )


def _running(name: str) -> bool:
    installed, state = service_admin._service_state(name)
    return installed and state == "running"


def _wait_running(name: str, *, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _running(name):
            return True
        time.sleep(0.5)
    return _running(name)


def accept_runtime_services(
    *,
    state_path: Path,
    exercise_watchdog_recovery: bool = False,
    timeout_seconds: float = 45.0,
) -> RuntimeServiceAcceptance:
    if not isinstance(state_path, Path) or not state_path.is_file():
        raise FileNotFoundError("canonical Sofía state database does not exist")
    if (
        not isinstance(timeout_seconds, (int, float))
        or timeout_seconds < 5
        or timeout_seconds > 300
    ):
        raise ValueError("timeout_seconds must be in 5..300")

    statuses = service_admin.validate_services(
        state_path=state_path,
    )
    registration_valid = all(item.valid for item in statuses)
    runtime_running = _running(RUNTIME_SERVICE.name)
    watchdog_running = _running(WATCHDOG_SERVICE.name)

    recovery_succeeded = False
    if exercise_watchdog_recovery:
        if not registration_valid:
            raise RuntimeError(
                "cannot exercise watchdog recovery with invalid registration"
            )
        if not runtime_running or not watchdog_running:
            raise RuntimeError(
                "runtime and watchdog must both be running before recovery test"
            )
        _, util = service_admin._require_windows()
        util.StopService(RUNTIME_SERVICE.name)
        recovery_succeeded = _wait_running(
            RUNTIME_SERVICE.name,
            timeout_seconds=timeout_seconds,
        )
        if not recovery_succeeded:
            # Best-effort restore of the runtime before reporting failure.
            try:
                util.StartService(RUNTIME_SERVICE.name)
            except Exception:
                pass
        runtime_running = _running(RUNTIME_SERVICE.name)
        watchdog_running = _running(WATCHDOG_SERVICE.name)

    return RuntimeServiceAcceptance(
        registration_valid=registration_valid,
        runtime_running=runtime_running,
        watchdog_running=watchdog_running,
        recovery_exercised=exercise_watchdog_recovery,
        recovery_succeeded=(
            recovery_succeeded
            if exercise_watchdog_recovery
            else False
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.run.windows_acceptance"
    )
    parser.add_argument("--state-path")
    parser.add_argument(
        "--exercise-watchdog-recovery",
        action="store_true",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
    )
    args = parser.parse_args(argv)

    state_path = (
        Path(args.state_path)
        if args.state_path
        else production_state_path()
    )
    try:
        result = accept_runtime_services(
            state_path=state_path,
            exercise_watchdog_recovery=(
                args.exercise_watchdog_recovery
            ),
            timeout_seconds=args.timeout_seconds,
        )
        print(
            "RUN Windows acceptance: "
            f"registration={result.registration_valid}; "
            f"runtime_running={result.runtime_running}; "
            f"watchdog_running={result.watchdog_running}; "
            f"recovery_exercised={result.recovery_exercised}; "
            f"recovery_succeeded={result.recovery_succeeded}; "
            f"accepted={result.accepted}"
        )
        return 0 if result.accepted else 2
    except Exception as exc:
        print(
            f"RUN Windows acceptance failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
