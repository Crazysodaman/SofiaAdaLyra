from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
from uuid import UUID
import time

from .fleet import FleetRegistry
from .model import FleetHost, HostLifecycle, HostTelemetry


class FleetPersistenceError(RuntimeError):
    pass


def _replace_with_retry(
    source: Path,
    target: Path,
    *,
    attempts: int = 8,
    initial_delay_seconds: float = 0.025,
) -> None:
    """Atomically replace target, tolerating transient Windows/SMB denial.

    Windows SMB shares can briefly deny an otherwise valid replace while an
    oplock/metadata update is settling. Retrying the same atomic replace keeps
    durability semantics intact. We intentionally do not delete the target as
    a fallback because that would create a non-atomic loss window.
    """

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds cannot be negative")

    delay = initial_delay_seconds
    last_error: PermissionError | None = None

    for attempt in range(attempts):
        try:
            source.replace(target)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            time.sleep(delay)
            delay = min(delay * 2, 0.25)

    raise FleetPersistenceError(
        f"atomic Fleet registry replace failed after {attempts} attempts: {target}"
    ) from last_error


class JsonFleetRegistry(FleetRegistry):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        if path.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for raw in data.get("hosts", []):
            tele = raw.pop("telemetry", None)
            if tele:
                tele["observed_at"] = datetime.fromisoformat(tele["observed_at"])
                tele = HostTelemetry(**tele)
            raw["lifecycle"] = HostLifecycle(raw["lifecycle"])
            raw["tags"] = tuple(raw.get("tags", ()))
            raw["node_id"] = (
                None
                if raw.get("node_id") is None
                else UUID(raw["node_id"])
            )
            self._hosts[raw["host_id"]] = FleetHost(telemetry=tele, **raw)

    def _mutate_and_flush(self, operation):
        before = dict(self._hosts)
        try:
            result = operation()
            self.flush()
            return result
        except Exception:
            self._hosts = before
            raise

    def register_candidate(self, host: FleetHost) -> None:
        self._mutate_and_flush(lambda: super(JsonFleetRegistry, self).register_candidate(host))

    def transition(self, host_id: str, state: HostLifecycle) -> FleetHost:
        return self._mutate_and_flush(
            lambda: super(JsonFleetRegistry, self).transition(host_id, state)
        )

    def refine_candidate_identity(
        self,
        host_id: str,
        *,
        platform: str,
        architecture: str,
        tags: tuple[str, ...] | None = None,
    ) -> FleetHost:
        return self._mutate_and_flush(
            lambda: super(JsonFleetRegistry, self).refine_candidate_identity(
                host_id,
                platform=platform,
                architecture=architecture,
                tags=tags,
            )
        )

    def authenticate_candidate(self, host_id: str, node_id: UUID) -> FleetHost:
        return self._mutate_and_flush(
            lambda: super(JsonFleetRegistry, self).authenticate_candidate(
                host_id,
                node_id,
            )
        )

    def update_telemetry(self, host_id: str, telemetry) -> FleetHost:
        return self._mutate_and_flush(
            lambda: super(JsonFleetRegistry, self).update_telemetry(host_id, telemetry)
        )

    def decommission(self, *args, **kwargs) -> FleetHost:
        return self._mutate_and_flush(
            lambda: super(JsonFleetRegistry, self).decommission(*args, **kwargs)
        )

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        hosts = []
        for host in self.hosts():
            telemetry = (
                None
                if host.telemetry is None
                else {
                    **host.telemetry.__dict__,
                    "observed_at": host.telemetry.observed_at.isoformat(),
                }
            )
            hosts.append(
                {
                    "host_id": host.host_id,
                    "platform": host.platform,
                    "architecture": host.architecture,
                    "lifecycle": host.lifecycle.value,
                    "trusted": host.trusted,
                    "telemetry": telemetry,
                    "tags": list(host.tags),
                    "node_id": (
                        None
                        if host.node_id is None
                        else str(host.node_id)
                    ),
                }
            )

        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump({"hosts": hosts}, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

        _replace_with_retry(temp, self.path)
