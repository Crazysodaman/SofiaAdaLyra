from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
import argparse
import socket
import sys
import time

from sofia.application.release_runtime import create_release_manager
from sofia.config import (
    create_production_configuration,
    production_state_path,
)
from sofia.integrations.local_maintenance import LocalMaintenanceAdapter
from sofia.run.lease import LocalRunLeaseStore, RunLease
from sofia.run.release import ReleaseRecoveryHook
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.state.component_schema import verify_production_component_schemas
from sofia.run.supervisor import (
    LocalRuntimeSupervisor,
    ManagedRuntimeBackend,
    ProcessState,
    RuntimeObservation,
)


class LocalServiceRuntimeBackend(ManagedRuntimeBackend):
    """Typed OS-service backend for the canonical Sofía runtime service."""

    def __init__(
        self,
        *,
        service_name: str,
        maintenance: LocalMaintenanceAdapter | None = None,
    ) -> None:
        if not isinstance(service_name, str) or not service_name.strip():
            raise ValueError("service_name must be nonempty")
        self.service_name = service_name.strip()
        self.maintenance = maintenance or LocalMaintenanceAdapter()

    def observe(self) -> RuntimeObservation:
        state = self.maintenance.service_status(self.service_name)
        if state == "running":
            return RuntimeObservation(
                ProcessState.RUNNING,
                ready=True,
                detail="service manager reports running",
            )
        if state == "starting":
            return RuntimeObservation(
                ProcessState.STARTING,
                ready=False,
                detail="service manager reports transitional state",
            )
        if state == "stopped":
            return RuntimeObservation(
                ProcessState.STOPPED,
                ready=False,
                detail="service manager reports stopped",
            )
        if state == "failed":
            return RuntimeObservation(
                ProcessState.FAILED,
                ready=False,
                detail="service manager reports failed",
            )
        return RuntimeObservation(
            ProcessState.UNKNOWN,
            ready=False,
            detail="service manager status is unknown",
        )

    def start(self, *, epoch: int) -> None:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("epoch must be a positive integer")
        self.maintenance.service(self.service_name, "start")

    def stop(self) -> None:
        self.maintenance.service(self.service_name, "stop")


@dataclass(slots=True)
class RunSupervisorHost:
    """Standalone watchdog host for one canonical local Sofía service."""

    state_path: Path
    service_name: str
    owner_id: str
    poll_seconds: float = 5.0
    lease_ttl_seconds: int = 30

    def __post_init__(self) -> None:
        if not isinstance(self.state_path, Path):
            raise TypeError("state_path must be a Path")
        if not self.state_path.is_file():
            raise FileNotFoundError(
                "existing Sofía state database required"
            )
        if not isinstance(self.service_name, str) or not self.service_name.strip():
            raise ValueError("service_name must be nonempty")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be nonempty")
        if not isinstance(self.poll_seconds, (int, float)) or self.poll_seconds < 1:
            raise ValueError("poll_seconds must be at least 1 second")
        if type(self.lease_ttl_seconds) is not int or not (
            5 <= self.lease_ttl_seconds <= 300
        ):
            raise ValueError("lease_ttl_seconds must be in 5..300")
        if self.poll_seconds >= self.lease_ttl_seconds:
            raise ValueError("poll interval must be shorter than lease TTL")

    def _supervisor(self) -> tuple[LocalRunLeaseStore, LocalRuntimeSupervisor]:
        configuration = replace(
            create_production_configuration(
                state_path=self.state_path,
            ),
            state_path=self.state_path,
        )
        verify_production_component_schemas(self.state_path)
        lease_store = LocalRunLeaseStore(self.state_path)
        manager = create_release_manager(
            configuration=configuration,
            state_plane=SQLiteStatePlane(self.state_path),
        )
        recovery = None if manager is None else ReleaseRecoveryHook(manager)
        supervisor = LocalRuntimeSupervisor(
            state_path=self.state_path,
            lease_store=lease_store,
            backend=LocalServiceRuntimeBackend(
                service_name=self.service_name,
            ),
            release_recovery=recovery,
        )
        return lease_store, supervisor

    def run(
        self,
        *,
        stop_event: Event | None = None,
    ) -> None:
        stopper = stop_event or Event()
        lease_store, supervisor = self._supervisor()
        result = lease_store.acquire(
            owner_id=self.owner_id,
            now=datetime.now(timezone.utc),
            ttl_seconds=self.lease_ttl_seconds,
        )
        lease = result.lease
        if lease is None:
            raise RuntimeError(
                "RUN watchdog could not acquire the local runtime lease: "
                f"{result.status}"
            )

        try:
            while not stopper.is_set():
                now = datetime.now(timezone.utc)
                renewed = lease_store.renew(
                    lease,
                    now=now,
                    ttl_seconds=self.lease_ttl_seconds,
                )
                if renewed.lease is None:
                    raise RuntimeError(
                        "RUN watchdog lost the local runtime lease"
                    )
                lease = renewed.lease
                supervisor.reconcile(
                    lease,
                    now=now,
                    desired_running=True,
                    stop_requested=False,
                )
                stopper.wait(self.poll_seconds)
        finally:
            lease_store.release(
                lease,
                now=datetime.now(timezone.utc),
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.run.host"
    )
    parser.add_argument(
        "--service",
        default="SofiaAdaLyra",
    )
    parser.add_argument(
        "--owner-id",
        default=f"run-watchdog:{socket.gethostname()}",
    )
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    parser.add_argument("--lease-ttl-seconds", type=int, default=30)
    parser.add_argument("--state-path")
    args = parser.parse_args(argv)

    try:
        host = RunSupervisorHost(
            state_path=(
                Path(args.state_path)
                if args.state_path
                else production_state_path()
            ),
            service_name=args.service,
            owner_id=args.owner_id,
            poll_seconds=args.poll_seconds,
            lease_ttl_seconds=args.lease_ttl_seconds,
        )
        host.run()
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"RUN supervisor refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
