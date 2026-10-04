"""Protected Fleet release canary/wave rollout and convergence journal."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import time
from typing import Any, Callable, Mapping, Protocol

from sofia.state.model import StateClass, StateKey, StateRecord
from sofia.state.plane import StatePlane


class RolloutRing(str, Enum):
    CANARY = "canary"
    NORMAL = "normal"
    DELAYED = "delayed"


@dataclass(frozen=True, slots=True)
class ReleaseRolloutTarget:
    host_id: str
    ring: RolloutRing

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id must be nonempty")
        if not isinstance(self.ring, RolloutRing):
            raise TypeError("ring must be RolloutRing")


@dataclass(frozen=True, slots=True)
class ReleaseRolloutEvent:
    host_id: str
    ring: RolloutRing
    action: str
    outcome: str
    occurred_at: datetime
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ReleaseRolloutResult:
    rollout_id: str
    release_id: str
    manifest_sha256: str
    status: str
    events: tuple[ReleaseRolloutEvent, ...]


class ReleaseFleetOperator(Protocol):
    def stage(self, host_id: str, release_id: str, manifest_sha256: str) -> Mapping[str, Any]: ...
    def activate(self, host_id: str, release_id: str, manifest_sha256: str) -> Mapping[str, Any]: ...
    def current(self, host_id: str) -> Mapping[str, Any]: ...
    def restart_runtime(self, host_id: str) -> Mapping[str, Any]: ...
    def runtime_healthy(self, host_id: str) -> bool: ...
    def rollback(self, host_id: str, failed_release_id: str, reason: str) -> Mapping[str, Any]: ...


class ReleaseRolloutError(RuntimeError):
    pass


class ReleaseRolloutJournal:
    NAMESPACE = "release-rollout"

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane")
        self.state_plane = state_plane

    def record(self, result: ReleaseRolloutResult, *, now: datetime) -> None:
        key = StateKey(self.NAMESPACE, result.rollout_id)
        existing = self.state_plane.read(key)
        payload = json.dumps(
            {
                "rollout_id": result.rollout_id,
                "release_id": result.release_id,
                "manifest_sha256": result.manifest_sha256,
                "status": result.status,
                "events": [
                    {
                        "host_id": event.host_id,
                        "ring": event.ring.value,
                        "action": event.action,
                        "outcome": event.outcome,
                        "occurred_at": event.occurred_at.isoformat(),
                        "detail": event.detail[:1000],
                    }
                    for event in result.events
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.state_plane.write(
            StateRecord(
                key=key,
                state_class=StateClass.PROTECTED,
                revision=1 if existing is None else existing.revision + 1,
                value=payload,
                updated_at=now.astimezone(timezone.utc),
                source="run:release-rollout",
            ),
            expected_revision=None if existing is None else existing.revision,
        )

    def get(self, rollout_id: str) -> dict[str, Any] | None:
        record = self.state_plane.read(StateKey(self.NAMESPACE, rollout_id))
        return None if record is None else json.loads(record.value.decode("utf-8"))


class ReleaseRolloutCoordinator:
    """Roll out canary -> normal -> delayed and roll back on any failed wave."""

    def __init__(
        self,
        *,
        state_plane: StatePlane,
        operator: ReleaseFleetOperator,
        health_attempts: int = 10,
        health_interval_seconds: float = 3.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane")
        if type(health_attempts) is not int or health_attempts < 1:
            raise ValueError("health_attempts must be positive")
        if (
            isinstance(health_interval_seconds, bool)
            or not isinstance(health_interval_seconds, (int, float))
            or health_interval_seconds < 0
        ):
            raise ValueError("health_interval_seconds must be nonnegative")
        if not callable(sleeper):
            raise TypeError("sleeper must be callable")
        self.state_plane = state_plane
        self.operator = operator
        self.health_attempts = health_attempts
        self.health_interval_seconds = float(health_interval_seconds)
        self.sleeper = sleeper
        self.journal = ReleaseRolloutJournal(state_plane)

    @staticmethod
    def _validate_targets(targets: tuple[ReleaseRolloutTarget, ...]) -> None:
        if not targets:
            raise ValueError("release rollout requires at least one target")
        if len({target.host_id for target in targets}) != len(targets):
            raise ValueError("release rollout target hosts must be unique")
        if len(targets) > 1 and not any(
            target.ring is RolloutRing.CANARY for target in targets
        ):
            raise ValueError("multi-host rollout requires at least one canary")

    @staticmethod
    def _event(
        events: list[ReleaseRolloutEvent],
        target: ReleaseRolloutTarget,
        action: str,
        outcome: str,
        detail: str = "",
    ) -> None:
        events.append(
            ReleaseRolloutEvent(
                target.host_id,
                target.ring,
                action,
                outcome,
                datetime.now(timezone.utc),
                detail,
            )
        )

    def _verify(
        self,
        target: ReleaseRolloutTarget,
        release_id: str,
        manifest_sha256: str,
        events: list[ReleaseRolloutEvent],
    ) -> None:
        current = self.operator.current(target.host_id)
        if (
            current.get("active") is not True
            or current.get("release_id") != release_id
            or current.get("manifest_sha256") != manifest_sha256
        ):
            raise ReleaseRolloutError(
                f"{target.host_id} did not converge to requested release"
            )
        self._event(events, target, "verify", "success")

    def _restart_and_wait_healthy(
        self,
        target: ReleaseRolloutTarget,
        events: list[ReleaseRolloutEvent],
    ) -> None:
        self.operator.restart_runtime(target.host_id)
        self._event(events, target, "runtime_restart", "success")
        for attempt in range(self.health_attempts):
            if self.operator.runtime_healthy(target.host_id):
                self._event(events, target, "runtime_health", "success")
                return
            if (
                attempt + 1 < self.health_attempts
                and self.health_interval_seconds > 0
            ):
                self.sleeper(self.health_interval_seconds)
        raise ReleaseRolloutError(
            f"{target.host_id} runtime did not become healthy after restart"
        )

    def rollout(
        self,
        *,
        rollout_id: str,
        release_id: str,
        manifest_sha256: str,
        targets: tuple[ReleaseRolloutTarget, ...],
    ) -> ReleaseRolloutResult:
        if not rollout_id.strip() or not release_id.strip():
            raise ValueError("rollout_id and release_id are required")
        if len(manifest_sha256) != 64:
            raise ValueError("manifest_sha256 must be SHA-256 text")
        try:
            int(manifest_sha256, 16)
        except ValueError as exc:
            raise ValueError("manifest_sha256 must be SHA-256 text") from exc
        manifest_sha256 = manifest_sha256.casefold()
        self._validate_targets(targets)
        events: list[ReleaseRolloutEvent] = []
        activated: list[ReleaseRolloutTarget] = []

        self.journal.record(
            ReleaseRolloutResult(
                rollout_id,
                release_id,
                manifest_sha256,
                "in_progress",
                (),
            ),
            now=datetime.now(timezone.utc),
        )

        try:
            for ring in (RolloutRing.CANARY, RolloutRing.NORMAL, RolloutRing.DELAYED):
                wave = tuple(target for target in targets if target.ring is ring)
                if not wave:
                    continue

                for target in wave:
                    self.operator.stage(
                        target.host_id,
                        release_id,
                        manifest_sha256,
                    )
                    self._event(events, target, "stage", "success")

                for target in wave:
                    self.operator.activate(
                        target.host_id,
                        release_id,
                        manifest_sha256,
                    )
                    activated.append(target)
                    self._event(events, target, "activate", "success")
                    self._restart_and_wait_healthy(target, events)
                    self._verify(
                        target,
                        release_id,
                        manifest_sha256,
                        events,
                    )

                self.journal.record(
                    ReleaseRolloutResult(
                        rollout_id,
                        release_id,
                        manifest_sha256,
                        f"{ring.value}_accepted",
                        tuple(events),
                    ),
                    now=datetime.now(timezone.utc),
                )

            for target in targets:
                self._verify(
                    target,
                    release_id,
                    manifest_sha256,
                    events,
                )

            complete = ReleaseRolloutResult(
                rollout_id,
                release_id,
                manifest_sha256,
                "completed",
                tuple(events),
            )
            self.journal.record(complete, now=datetime.now(timezone.utc))
            return complete
        except Exception as exc:
            rollback_errors: list[str] = []
            for target in reversed(activated):
                try:
                    self.operator.rollback(
                        target.host_id,
                        release_id,
                        f"rollout {rollout_id} failed: {type(exc).__name__}",
                    )
                    self._restart_and_wait_healthy(target, events)
                    self._event(events, target, "rollback", "success")
                except Exception as rollback_exc:
                    rollback_errors.append(
                        f"{target.host_id}:{type(rollback_exc).__name__}"
                    )
                    self._event(
                        events,
                        target,
                        "rollback",
                        "failed",
                        type(rollback_exc).__name__,
                    )
            failed = ReleaseRolloutResult(
                rollout_id,
                release_id,
                manifest_sha256,
                "rollback_incomplete" if rollback_errors else "rolled_back",
                tuple(events),
            )
            self.journal.record(failed, now=datetime.now(timezone.utc))
            detail = f"{type(exc).__name__}: {exc}"
            if rollback_errors:
                detail += "; rollback=" + ",".join(rollback_errors)
            raise ReleaseRolloutError(detail) from exc


class RemoteFleetReleaseOperator:
    """Adapter over the existing pinned-mTLS Fleet service."""

    def __init__(
        self,
        *,
        remote_service,
        host_node_lookup: Callable[[str], str],
        runtime_service_name: str,
    ) -> None:
        if remote_service is None:
            raise ValueError("remote_service is required")
        if not callable(host_node_lookup):
            raise TypeError("host_node_lookup must be callable")
        if (
            not isinstance(runtime_service_name, str)
            or not runtime_service_name.strip()
        ):
            raise ValueError("runtime_service_name must be nonempty")
        self.remote_service = remote_service
        self.host_node_lookup = host_node_lookup
        self.runtime_service_name = runtime_service_name.strip()

    def _call(
        self,
        host_id: str,
        capability: str,
        operation: str,
        parameters: dict[str, Any],
    ):
        return self.remote_service.invoke(
            self.host_node_lookup(host_id),
            capability,
            operation,
            parameters,
        )

    def stage(self, host_id: str, release_id: str, manifest_sha256: str):
        return self._call(
            host_id,
            "release.manage",
            "stage",
            {"release_id": release_id, "manifest_sha256": manifest_sha256},
        )

    def activate(self, host_id: str, release_id: str, manifest_sha256: str):
        return self._call(
            host_id,
            "release.manage",
            "activate",
            {"release_id": release_id, "manifest_sha256": manifest_sha256},
        )

    def current(self, host_id: str):
        result = self._call(host_id, "release.inspect", "current", {})
        message = result.get("message", "")
        try:
            payload = json.loads(message) if message else {}
        except (TypeError, json.JSONDecodeError) as exc:
            raise ReleaseRolloutError(
                f"{host_id} returned invalid release status"
            ) from exc
        if not isinstance(payload, dict):
            raise ReleaseRolloutError(
                f"{host_id} release status is not an object"
            )
        return payload

    def restart_runtime(self, host_id: str):
        return self._call(
            host_id,
            "service.manage",
            "restart",
            {"service": self.runtime_service_name},
        )

    def runtime_healthy(self, host_id: str) -> bool:
        result = self._call(
            host_id,
            "system.inspect",
            "service",
            {"name": self.runtime_service_name, "limit": 1},
        )
        if result.get("outcome") != "reported_success":
            return False
        message = result.get("message", "")
        try:
            payload = json.loads(message) if message else {}
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        if str(payload.get("kind", "")).casefold() != "success":
            return False
        evidence = payload.get("evidence")
        if not isinstance(evidence, dict):
            return False
        services = evidence.get("services")
        if not isinstance(services, list) or len(services) != 1:
            return False
        service = services[0]
        if not isinstance(service, dict):
            return False
        if str(service.get("name", "")) != self.runtime_service_name:
            return False
        return str(service.get("state", "")).casefold() in {
            "running",
            "active",
        }

    def rollback(self, host_id: str, failed_release_id: str, reason: str):
        return self._call(
            host_id,
            "release.manage",
            "rollback",
            {"failed_release_id": failed_release_id, "reason": reason},
        )
