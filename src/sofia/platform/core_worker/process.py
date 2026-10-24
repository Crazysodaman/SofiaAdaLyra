"""Spawned Core cognition worker with HMAC-authenticated local IPC."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import base64
import json
import multiprocessing
from multiprocessing.connection import Client, Connection, Listener
import os
from pathlib import Path
from queue import Queue
import secrets
import time
from threading import Thread
from typing import Mapping
from typing import Callable

from sofia.core.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.core.cognition.llm_engine import LLMCognitiveEngine
from sofia.core.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.core.cognition.rules import RuleEngine
from sofia.core.cognition.test_engine import TestCognitiveEngine
from sofia.platform.cognition_provider import create_llm_provider
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.run.generation import ComponentGenerationStore
from sofia.platform.run.lease import RunLease
from sofia.platform.run.supervisor import (
    ManagedRuntimeBackend, ProcessState, RuntimeObservation,
)
from sofia.sdk import (
    AuthorityProjection,
    ComponentEndpoint,
    ComponentKind,
    ComponentRequestEnvelope,
    ProtocolVersion,
    SDK_PROTOCOL_VERSION,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
)


MAX_IPC_BYTES = 1_400_000


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _send(connection: Connection, document: Mapping[str, object]) -> None:
    raw = json.dumps(
        dict(document), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if len(raw) > MAX_IPC_BYTES:
        raise ValueError("Core worker IPC message exceeds limit")
    connection.send_bytes(raw)


def _receive(connection: Connection) -> Mapping[str, object]:
    try:
        raw = connection.recv_bytes(MAX_IPC_BYTES)
        value = json.loads(raw.decode("utf-8"))
    except (EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoreWorkerError("Core worker IPC failed") from exc
    if not isinstance(value, dict):
        raise CoreWorkerError("Core worker IPC message must be an object")
    return value


@dataclass(frozen=True, slots=True)
class CoreEngineProcessSpec:
    kind: str
    provider: ProviderConfiguration | None = None
    test_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in {"rule", "test", "provider"}:
            raise ValueError("unsupported Core worker engine kind")
        if (self.kind == "provider") != (self.provider is not None):
            raise ValueError("provider engine requires exactly one provider configuration")
        if not isinstance(self.test_delay_seconds, (int, float)) or not (
            0 <= self.test_delay_seconds <= 30
        ):
            raise ValueError("test_delay_seconds must be in 0..30")
        if self.test_delay_seconds and self.kind != "test":
            raise ValueError("only the deterministic test engine may be delayed")

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "provider": None if self.provider is None else asdict(self.provider),
            "test_delay_seconds": self.test_delay_seconds,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "CoreEngineProcessSpec":
        if not isinstance(payload, dict) or set(payload) != {
            "kind", "provider", "test_delay_seconds"
        }:
            raise ValueError("invalid Core engine process specification")
        provider = payload["provider"]
        return cls(
            kind=payload["kind"],
            provider=None if provider is None else ProviderConfiguration(**provider),
            test_delay_seconds=payload["test_delay_seconds"],
        )


@dataclass(frozen=True, slots=True)
class CoreWorkerHealth:
    endpoint: ComponentEndpoint
    pid: int
    ready: bool
    accepting: bool


class CoreWorkerError(RuntimeError):
    pass


def _engine(spec: CoreEngineProcessSpec) -> CognitiveEngine:
    if spec.kind == "rule":
        return RuleEngine()
    if spec.kind == "test":
        return TestCognitiveEngine(ProviderConfiguration(provider="test", model="test"))
    assert spec.provider is not None
    provider = create_llm_provider(spec.provider)
    return LLMCognitiveEngine(spec.provider, provider)


def _worker_main(
    address: str, family: str, authkey: bytes, endpoint_payload: dict[str, object],
    spec_payload: dict[str, object],
) -> None:
    connection: Connection | None = None
    try:
        endpoint = ComponentEndpoint.from_payload(endpoint_payload)
        spec = CoreEngineProcessSpec.from_payload(spec_payload)
        engine = _engine(spec)
        connection = Client(address, family=family, authkey=authkey)
        accepting = True
        _send(connection, {
            "kind": "ready", "protocol": str(SDK_PROTOCOL_VERSION),
            "endpoint": endpoint.to_payload(), "pid": os.getpid(),
        })
        while True:
            message = _receive(connection)
            kind = message.get("kind")
            if kind == "health" and set(message) == {"kind"}:
                _send(connection, {
                    "kind": "health", "endpoint": endpoint.to_payload(),
                    "pid": os.getpid(), "ready": True, "accepting": accepting,
                })
                continue
            if kind == "drain" and set(message) == {"kind"}:
                accepting = False
                _send(connection, {"kind": "drained", "pid": os.getpid()})
                continue
            if kind == "shutdown" and set(message) == {"kind"}:
                _send(connection, {"kind": "stopped", "pid": os.getpid()})
                return
            if kind != "respond" or set(message) != {"kind", "envelope", "payload"}:
                raise CoreWorkerError("unsupported Core worker IPC command")
            if not accepting:
                _send(connection, {"kind": "error", "error": "worker_draining"})
                continue
            envelope = ComponentRequestEnvelope.from_payload(message["envelope"])
            if envelope.protocol != SDK_PROTOCOL_VERSION or envelope.destination != endpoint:
                raise PermissionError("Core worker request identity is incompatible")
            envelope.require_dispatchable(
                now=datetime.now(timezone.utc),
                expected_destination_generation=endpoint.generation,
            )
            encoded = base64.b64decode(message["payload"], validate=True)
            if sha256(encoded).hexdigest() != envelope.payload_digest:
                raise PermissionError("Core worker request digest mismatch")
            try:
                if spec.test_delay_seconds:
                    time.sleep(spec.test_delay_seconds)
                response = engine.respond(decode_request(encoded))
                result = encode_response(response)
                _send(connection, {
                    "kind": "response", "request_id": envelope.request_id,
                    "payload": base64.b64encode(result).decode("ascii"),
                    "payload_digest": sha256(result).hexdigest(),
                })
            except Exception as exc:
                _send(connection, {
                    "kind": "error", "request_id": envelope.request_id,
                    "error": type(exc).__name__,
                })
    except BaseException:
        # The parent observes EOF/process exit and records crash/uncertainty.
        return
    finally:
        if connection is not None:
            connection.close()


class _CoreWorkerProcess:
    def __init__(
        self, *, endpoint: ComponentEndpoint, spec: CoreEngineProcessSpec,
        runtime_dir: Path, startup_timeout: float = 10.0,
    ) -> None:
        self.endpoint = endpoint
        self.spec = spec
        self.runtime_dir = runtime_dir
        self.startup_timeout = startup_timeout
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._listener: Listener | None = None
        self._socket_path = runtime_dir / (
            f"core-{endpoint.component_id.replace('.', '-')}-{endpoint.generation}.sock"
        )
        self._family = "AF_PIPE" if os.name == "nt" else "AF_UNIX"
        self._address = (
            rf"\\.\pipe\sofia-core-{endpoint.generation}-{secrets.token_hex(8)}"
            if self._family == "AF_PIPE" else str(self._socket_path)
        )

    @property
    def pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self) -> CoreWorkerHealth:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self._family == "AF_UNIX" and (
            self._socket_path.exists() or self._socket_path.is_symlink()
        ):
            raise CoreWorkerError("Core worker socket path already exists")
        authkey = secrets.token_bytes(32)
        self._listener = Listener(
            self._address, family=self._family, authkey=authkey,
        )
        queue: Queue[object] = Queue(maxsize=1)
        def accept() -> None:
            try:
                queue.put(self._listener.accept())
            except BaseException as exc:
                queue.put(exc)
        thread = Thread(target=accept, daemon=True)
        thread.start()
        context = multiprocessing.get_context("spawn")
        self._process = context.Process(
            target=_worker_main,
            args=(self._address, self._family, authkey, self.endpoint.to_payload(),
                  self.spec.to_payload()),
            name=f"sofia-core-{self.endpoint.generation}", daemon=False,
        )
        self._process.start()
        thread.join(self.startup_timeout)
        if thread.is_alive() or queue.empty():
            self.terminate(force=True)
            raise CoreWorkerError("Core worker did not connect before startup deadline")
        accepted = queue.get()
        if isinstance(accepted, BaseException):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker authenticated connection failed") from accepted
        self._connection = accepted
        if not self._connection.poll(self.startup_timeout):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker did not become ready")
        ready = _receive(self._connection)
        expected = {"kind", "protocol", "endpoint", "pid"}
        if set(ready) != expected or ready["kind"] != "ready" or (
            ready["protocol"] != str(SDK_PROTOCOL_VERSION)
        ) or ComponentEndpoint.from_payload(ready["endpoint"]) != self.endpoint or (
            ready["pid"] != self.pid
        ):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker readiness identity mismatch")
        return CoreWorkerHealth(self.endpoint, self.pid or 0, True, True)

    def health(self, timeout: float = 2.0) -> CoreWorkerHealth:
        if self._connection is None or not self.alive:
            raise CoreWorkerError("Core worker is not connected")
        _send(self._connection, {"kind": "health"})
        if not self._connection.poll(timeout):
            raise CoreWorkerError("Core worker health deadline expired")
        value = _receive(self._connection)
        if set(value) != {"kind", "endpoint", "pid", "ready", "accepting"} or (
            value["kind"] != "health"
            or ComponentEndpoint.from_payload(value["endpoint"]) != self.endpoint
            or value["pid"] != self.pid
        ):
            raise CoreWorkerError("Core worker health identity mismatch")
        return CoreWorkerHealth(
            self.endpoint, value["pid"], value["ready"], value["accepting"]
        )

    def respond(
        self, *, envelope: ComponentRequestEnvelope,
        request: CognitiveRequest, timeout: float,
    ) -> CognitiveResponse:
        if self._connection is None or not self.alive:
            raise CoreWorkerError("Core worker is not connected")
        payload = encode_request(request)
        if sha256(payload).hexdigest() != envelope.payload_digest:
            raise ValueError("Core worker request envelope digest mismatch")
        _send(self._connection, {
            "kind": "respond", "envelope": envelope.to_payload(),
            "payload": base64.b64encode(payload).decode("ascii"),
        })
        if not self._connection.poll(timeout):
            raise TimeoutError("Core worker response deadline expired")
        value = _receive(self._connection)
        if value.get("kind") == "error":
            raise CoreWorkerError(f"Core worker failed: {value.get('error', 'unknown')}")
        if set(value) != {"kind", "request_id", "payload", "payload_digest"} or (
            value["kind"] != "response" or value["request_id"] != envelope.request_id
        ):
            raise CoreWorkerError("Core worker response identity mismatch")
        result = base64.b64decode(value["payload"], validate=True)
        if sha256(result).hexdigest() != value["payload_digest"]:
            raise CoreWorkerError("Core worker response digest mismatch")
        return decode_response(result)

    def drain(self, timeout: float = 5.0) -> None:
        if self._connection is None or not self.alive:
            raise CoreWorkerError("Core worker is not connected")
        _send(self._connection, {"kind": "drain"})
        if not self._connection.poll(timeout):
            raise TimeoutError("Core worker drain deadline expired")
        value = _receive(self._connection)
        if value != {"kind": "drained", "pid": self.pid}:
            raise CoreWorkerError("Core worker drain acknowledgement mismatch")

    def terminate(self, *, timeout: float = 5.0, force: bool = False) -> bool:
        process = self._process
        if process is None:
            return True
        graceful = False
        if not force and process.is_alive() and self._connection is not None:
            try:
                _send(self._connection, {"kind": "shutdown"})
                if self._connection.poll(timeout):
                    value = _receive(self._connection)
                    graceful = value == {"kind": "stopped", "pid": process.pid}
            except Exception:
                graceful = False
        process.join(timeout if graceful else 0.1)
        if process.is_alive():
            process.terminate()
            process.join(timeout)
        if process.is_alive():
            process.kill()
            process.join(timeout)
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._family == "AF_UNIX" and (
            self._socket_path.exists() or self._socket_path.is_symlink()
        ):
            self._socket_path.unlink()
        return not process.is_alive()


class CoreWorkerController:
    """RUN-authorized lifecycle and request owner for one Core identity."""

    def __init__(
        self, *, generations: ComponentGenerationStore, lease: RunLease,
        platform_instance_id: str, core_identity_id: str, component_id: str,
        runtime_dir: Path, response_timeout: timedelta = timedelta(minutes=2),
    ) -> None:
        self.generations = generations
        self.lease = lease
        self.platform_instance_id = platform_instance_id
        self.core_identity_id = core_identity_id
        self.component_id = component_id
        self.runtime_dir = runtime_dir
        self.response_timeout = response_timeout
        self._active: _CoreWorkerProcess | None = None

    @property
    def endpoint(self) -> ComponentEndpoint | None:
        return None if self._active is None else self._active.endpoint

    @property
    def pid(self) -> int | None:
        return None if self._active is None else self._active.pid

    @property
    def engine_spec(self) -> CoreEngineProcessSpec | None:
        return None if self._active is None else self._active.spec

    def _stage(
        self, release_digest: str, spec: CoreEngineProcessSpec, now: datetime,
    ) -> _CoreWorkerProcess:
        endpoint = self.generations.stage(
            component_id=self.component_id, kind=ComponentKind.CORE,
            release_digest=release_digest,
            platform_instance_id=self.platform_instance_id,
            core_identity_id=self.core_identity_id,
            lease=self.lease, now=now, reason="Core worker release staged",
        )
        return _CoreWorkerProcess(
            endpoint=endpoint, spec=spec, runtime_dir=self.runtime_dir,
        )

    def start(
        self, *, release_digest: str, spec: CoreEngineProcessSpec,
        now: datetime,
    ) -> CoreWorkerHealth:
        if self._active is not None:
            raise RuntimeError("Core worker is already active")
        process = self._stage(release_digest, spec, now)
        try:
            health = process.start()
        except Exception:
            self.generations.quarantine_staged(
                process.endpoint, lease=self.lease, now=now,
                reason="Core worker failed readiness",
            )
            raise
        try:
            self.generations.activate(
                process.endpoint, lease=self.lease, now=now,
                reason="authenticated readiness verified",
            )
        except Exception:
            process.terminate(force=True)
            self.generations.quarantine_staged(
                process.endpoint, lease=self.lease, now=now,
                reason="activation admission denied",
            )
            raise
        self._active = process
        return health

    def reconcile_startup(
        self, *, observe_running: Callable[[ComponentEndpoint], bool | None],
        now: datetime,
    ) -> str:
        """Reconcile a prior active row without reconnecting or replaying it.

        ``True`` means a process is still verified running, ``False`` means an
        authoritative probe verified it stopped, and ``None`` means unknown.
        Only verified-stopped state may be fenced automatically.
        """
        if not callable(observe_running):
            raise TypeError("observe_running must be callable")
        if self._active is not None:
            raise RuntimeError("startup reconciliation requires no local worker")
        active = self.generations.active_for_core_identity(self.core_identity_id)
        if active is None:
            return "no_prior_active_generation"
        observation = observe_running(active)
        if observation is None:
            raise CoreWorkerError("prior Core process outcome is unknown")
        if observation is True:
            raise CoreWorkerError(
                "prior Core process is running but has no authenticated recovered channel"
            )
        if observation is not False:
            raise TypeError("process observation must be bool or None")
        self.generations.begin_drain(
            active, lease=self.lease, now=now,
            reason="startup probe verified prior Core stopped",
        )
        self.generations.fence(
            active, lease=self.lease, now=now,
            reason="startup recovery fenced stopped Core", quarantine=True,
        )
        return "prior_stopped_generation_quarantined"

    def health(self) -> CoreWorkerHealth:
        if self._active is None or not self.generations.is_active(self._active.endpoint):
            raise CoreWorkerError("no active Core worker generation")
        try:
            return self._active.health()
        except Exception:
            process = self._active
            self._quarantine(
                process, now=datetime.now(timezone.utc), reason="health_failed",
            )
            raise

    def cancel(self, *, now: datetime, reason: str = "request cancelled") -> None:
        """Fence and stop the current worker; no request is replayed."""
        process = self._active
        if process is None:
            return
        self._quarantine(process, now=now, reason=reason)

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        process = self._active
        now = datetime.now(timezone.utc)
        if process is None or not self.generations.is_active(process.endpoint):
            raise CognitiveEngineError("Core worker generation is not active")
        current_lease = self.generations.lease_store.current(now=now)
        if current_lease is None or (
            current_lease.owner_id != self.lease.owner_id
            or current_lease.epoch != self.lease.epoch
        ):
            raise CognitiveEngineError("Core worker RUN authority expired")
        deadline = min(now + self.response_timeout, current_lease.expires_at)
        if deadline <= now:
            raise CognitiveEngineError("Core worker RUN authority expired")
        payload = encode_request(request)
        envelope = ComponentRequestEnvelope(
            protocol=SDK_PROTOCOL_VERSION,
            request_id=f"core-request:{secrets.token_hex(16)}",
            correlation_id=f"core-correlation:{secrets.token_hex(16)}",
            idempotency_key=f"core-idempotency:{secrets.token_hex(16)}",
            source=ComponentEndpoint(
                "platform.host", ComponentKind.PLATFORM,
                process.endpoint.release_digest, self.lease.epoch,
                self.platform_instance_id,
            ),
            destination=process.endpoint,
            authority=AuthorityProjection(
                principal_id="system:platform", audience_id="system:core",
                audience_kind="system",
                authority_ref=f"run:{self.lease.owner_id}:{self.lease.epoch}",
                scopes=("cognition.respond",), expires_at=current_lease.expires_at,
            ),
            payload_type="sofia.core.cognition.request.v1",
            payload_digest=sha256(payload).hexdigest(), created_at=now,
            deadline=deadline,
        )
        try:
            return process.respond(
                envelope=envelope, request=request,
                timeout=max(0.001, (deadline - now).total_seconds()),
            )
        except Exception as exc:
            self._quarantine(process, now=datetime.now(timezone.utc), reason=type(exc).__name__)
            raise CognitiveEngineError("Core worker request failed or became uncertain") from exc

    def _quarantine(self, process: _CoreWorkerProcess, *, now: datetime, reason: str) -> None:
        if self.generations.is_active(process.endpoint):
            self.generations.begin_drain(
                process.endpoint, lease=self.lease, now=now, reason=reason,
            )
        stopped = process.terminate(force=True)
        if stopped:
            self.generations.fence(
                process.endpoint, lease=self.lease, now=now, reason=reason,
                quarantine=True,
            )
        if process is self._active:
            self._active = None

    def replace(
        self, *, release_digest: str, spec: CoreEngineProcessSpec,
        now: datetime,
    ) -> CoreWorkerHealth:
        old = self._active
        if old is None or not self.generations.is_active(old.endpoint):
            raise CoreWorkerError("no active Core worker to replace")
        candidate = self._stage(release_digest, spec, now)
        try:
            health = candidate.start()
        except Exception:
            self.generations.quarantine_staged(
                candidate.endpoint, lease=self.lease, now=now,
                reason="replacement failed readiness",
            )
            raise
        self.generations.begin_drain(
            old.endpoint, lease=self.lease, now=now, reason="Core replacement",
        )
        drained = True
        try:
            old.drain()
        except Exception:
            drained = False
        if not old.terminate():
            candidate.terminate(force=True)
            self.generations.quarantine_staged(
                candidate.endpoint, lease=self.lease, now=now,
                reason="old Core termination unverified",
            )
            raise CoreWorkerError("old Core termination could not be verified")
        self.generations.fence(
            old.endpoint, lease=self.lease, now=now,
            reason=("old Core process exited" if drained else "old Core drain interrupted"),
            quarantine=not drained,
        )
        self.generations.activate(
            candidate.endpoint, lease=self.lease, now=now,
            reason="replacement readiness verified",
        )
        self._active = candidate
        return health

    def shutdown(self, *, now: datetime) -> None:
        process = self._active
        if process is None:
            return
        self.generations.begin_drain(
            process.endpoint, lease=self.lease, now=now, reason="Platform shutdown",
        )
        try:
            process.drain()
        except Exception:
            pass
        stopped = process.terminate()
        if stopped:
            self.generations.fence(
                process.endpoint, lease=self.lease, now=now,
                reason="Core worker stopped",
            )
        self._active = None


class CoreWorkerCognitiveEngine(CognitiveEngine):
    def __init__(self, controller: CoreWorkerController) -> None:
        if not isinstance(controller, CoreWorkerController):
            raise TypeError("controller must be CoreWorkerController")
        self.controller = controller

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        return self.controller.respond(request)


class CoreWorkerRuntimeBackend(ManagedRuntimeBackend):
    """Existing ComponentRuntimeSupervisor adapter for the Core process."""

    def __init__(
        self, *, controller: CoreWorkerController, release_digest: str,
        spec: CoreEngineProcessSpec,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(controller, CoreWorkerController):
            raise TypeError("controller must be CoreWorkerController")
        if not isinstance(release_digest, str) or len(release_digest) != 64:
            raise ValueError("release_digest must be SHA-256")
        if not isinstance(spec, CoreEngineProcessSpec):
            raise TypeError("spec must be CoreEngineProcessSpec")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self.controller = controller
        self.release_digest = release_digest
        self.spec = spec
        self.clock = clock

    def observe(self) -> RuntimeObservation:
        if self.controller.endpoint is None:
            return RuntimeObservation(ProcessState.STOPPED, detail="no active Core generation")
        try:
            health = self.controller.health()
        except Exception:
            return RuntimeObservation(ProcessState.FAILED, detail="Core health failed")
        return RuntimeObservation(
            ProcessState.RUNNING, ready=health.ready and health.accepting,
            detail=f"authenticated Core generation {health.endpoint.generation}",
        )

    def start(self, *, epoch: int) -> None:
        if type(epoch) is not int or epoch != self.controller.lease.epoch:
            raise PermissionError("component supervisor RUN epoch mismatch")
        if self.controller.endpoint is None:
            self.controller.start(
                release_digest=self.release_digest, spec=self.spec, now=self.clock(),
            )

    def stop(self) -> None:
        self.controller.shutdown(now=self.clock())
