"""Spawned Core cognition worker with HMAC-authenticated local IPC."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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
from threading import Event, RLock, Thread
from typing import Mapping
from typing import Callable
from uuid import uuid4

from sofia.core.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.core.cognition.llm_engine import LLMCognitiveEngine
from sofia.core.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.core.cognition.provider import LLMProvider, LLMProviderError
from sofia.core.cognition.rules import RuleEngine
from sofia.core.cognition.test_engine import TestCognitiveEngine
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.run.generation import ComponentGenerationStore
from sofia.platform.run.lease import LocalRunLeaseStore, RunLease
from sofia.platform.run.components import (
    ComponentKind as SupervisedComponentKind,
    ComponentRuntimeSupervisor,
    ComponentSpec,
)
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


def installed_core_release_digest(package_root: Path | None = None) -> str:
    """Hash the actual installed Sofía package bytes used by a worker.

    Bytecode/cache files are execution artifacts rather than release inputs.
    Symlinks are rejected so a digest can never attest to a redirected tree.
    """
    root = (
        package_root.resolve()
        if package_root is not None
        else Path(__file__).resolve().parents[2]
    )
    if not root.is_dir():
        raise FileNotFoundError("installed Sofía package root is missing")
    digest = sha256()
    paths = sorted(
        (
            path for path in root.rglob("*")
            if path.is_symlink()
            or (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix not in {".pyc", ".pyo"}
            )
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not paths:
        raise CoreWorkerError("installed Sofía package contains no release files")
    for path in paths:
        if path.is_symlink():
            raise CoreWorkerError(
                f"installed Sofía package contains symlink: {path.relative_to(root)}"
            )
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or len(data) != after.st_size
        ):
            raise CoreWorkerError("installed Sofía package changed during attestation")
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _endpoint_token(endpoint: ComponentEndpoint) -> str:
    raw = json.dumps(
        endpoint.to_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(raw).hexdigest()


class _ProcessLifetimeLock:
    """Cross-platform, process-owned lifetime evidence for crash recovery."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError):
            handle.close()
            raise
        self._file = handle

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._file = None

    @classmethod
    def observe_running(cls, path: Path) -> bool | None:
        if not path.is_file():
            return None
        probe = cls(path)
        try:
            probe.acquire()
        except (OSError, BlockingIOError):
            return True
        else:
            probe.release()
            return False


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
    secondary_provider: ProviderConfiguration | None = None
    test_delay_seconds: float = 0.0
    test_startup_delay_seconds: float = 0.0
    expected_runtime_digest: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"rule", "test", "provider"}:
            raise ValueError("unsupported Core worker engine kind")
        if (self.kind == "provider") != (self.provider is not None):
            raise ValueError("provider engine requires exactly one provider configuration")
        if self.secondary_provider is not None and self.kind != "provider":
            raise ValueError("secondary provider requires a provider engine")
        if not isinstance(self.test_delay_seconds, (int, float)) or not (
            0 <= self.test_delay_seconds <= 30
        ):
            raise ValueError("test_delay_seconds must be in 0..30")
        if self.test_delay_seconds and self.kind != "test":
            raise ValueError("only the deterministic test engine may be delayed")
        if not isinstance(self.test_startup_delay_seconds, (int, float)) or not (
            0 <= self.test_startup_delay_seconds <= 30
        ):
            raise ValueError("test_startup_delay_seconds must be in 0..30")
        if self.test_startup_delay_seconds and self.kind != "test":
            raise ValueError("only the deterministic test startup may be delayed")
        if self.expected_runtime_digest is not None and (
            len(self.expected_runtime_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.expected_runtime_digest
            )
        ):
            raise ValueError("expected_runtime_digest must be SHA-256 or None")

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "provider": None if self.provider is None else asdict(self.provider),
            "secondary_provider": (
                None
                if self.secondary_provider is None
                else asdict(self.secondary_provider)
            ),
            "test_delay_seconds": self.test_delay_seconds,
            "test_startup_delay_seconds": self.test_startup_delay_seconds,
            "expected_runtime_digest": self.expected_runtime_digest,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "CoreEngineProcessSpec":
        if not isinstance(payload, dict) or set(payload) != {
            "kind", "provider", "secondary_provider", "test_delay_seconds",
            "test_startup_delay_seconds", "expected_runtime_digest",
        }:
            raise ValueError("invalid Core engine process specification")
        provider = payload["provider"]
        secondary_provider = payload["secondary_provider"]
        return cls(
            kind=payload["kind"],
            provider=None if provider is None else ProviderConfiguration(**provider),
            secondary_provider=(
                None
                if secondary_provider is None
                else ProviderConfiguration(**secondary_provider)
            ),
            test_delay_seconds=payload["test_delay_seconds"],
            test_startup_delay_seconds=payload["test_startup_delay_seconds"],
            expected_runtime_digest=payload["expected_runtime_digest"],
        )


@dataclass(frozen=True, slots=True)
class CoreWorkerHealth:
    endpoint: ComponentEndpoint
    pid: int
    ready: bool
    accepting: bool


class CoreWorkerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlatformProviderBinding:
    """Exact Platform-owned provider made callable by one Core generation.

    The provider object deliberately stays in the Platform process.  Only its
    provider-neutral request/response contract crosses the authenticated Core
    channel; constructing this binding grants no tool or execution authority.
    """

    configuration: ProviderConfiguration
    provider: LLMProvider

    def __post_init__(self) -> None:
        if not isinstance(self.configuration, ProviderConfiguration):
            raise TypeError("configuration must be ProviderConfiguration")
        if not isinstance(self.provider, LLMProvider):
            raise TypeError("provider must implement LLMProvider")


def _configuration_digest(configuration: ProviderConfiguration) -> str:
    payload = json.dumps(
        asdict(configuration), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


class _PlatformProviderProxy(LLMProvider):
    """Core-side authority-free proxy for a Platform-owned provider."""

    def __init__(
        self, *, connection: Connection, role: str,
        configuration: ProviderConfiguration,
    ) -> None:
        self.connection = connection
        self.role = role
        self.configuration_digest = _configuration_digest(configuration)

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        payload = encode_request(request)
        request_id = f"provider:{secrets.token_hex(16)}"
        _send(self.connection, {
            "kind": "provider_request",
            "request_id": request_id,
            "role": self.role,
            "configuration_digest": self.configuration_digest,
            "payload": base64.b64encode(payload).decode("ascii"),
            "payload_digest": sha256(payload).hexdigest(),
        })
        value = _receive(self.connection)
        if value.get("kind") == "provider_error" and (
            value.get("request_id") == request_id
        ):
            raise LLMProviderError("Platform provider request failed")
        if set(value) != {
            "kind", "request_id", "configuration_digest", "payload",
            "payload_digest",
        } or value["kind"] != "provider_response" or (
            value["request_id"] != request_id
            or value["configuration_digest"] != self.configuration_digest
        ):
            raise LLMProviderError("Platform provider response identity mismatch")
        result = base64.b64decode(value["payload"], validate=True)
        if sha256(result).hexdigest() != value["payload_digest"]:
            raise LLMProviderError("Platform provider response digest mismatch")
        return decode_response(result)


def _engines(
    spec: CoreEngineProcessSpec, connection: Connection,
) -> dict[str, CognitiveEngine]:
    if spec.kind == "rule":
        return {"primary": RuleEngine()}
    if spec.kind == "test":
        return {
            "primary": TestCognitiveEngine(
                ProviderConfiguration(provider="test", model="test")
            )
        }
    assert spec.provider is not None
    engines: dict[str, CognitiveEngine] = {
        "primary": LLMCognitiveEngine(
            spec.provider,
            _PlatformProviderProxy(
                connection=connection, role="primary",
                configuration=spec.provider,
            ),
        )
    }
    if spec.secondary_provider is not None:
        engines["secondary"] = LLMCognitiveEngine(
            spec.secondary_provider,
            _PlatformProviderProxy(
                connection=connection, role="secondary",
                configuration=spec.secondary_provider,
            ),
        )
    return engines


def _worker_main(
    address: str, family: str, authkey: bytes, endpoint_payload: dict[str, object],
    spec_payload: dict[str, object], lifetime_lock_path: str,
) -> None:
    connection: Connection | None = None
    lifetime_lock = _ProcessLifetimeLock(Path(lifetime_lock_path))
    try:
        endpoint = ComponentEndpoint.from_payload(endpoint_payload)
        lifetime_lock.acquire()
        spec = CoreEngineProcessSpec.from_payload(spec_payload)
        connection = Client(address, family=family, authkey=authkey)
        _send(connection, {
            "kind": "starting", "protocol": str(SDK_PROTOCOL_VERSION),
            "endpoint": endpoint.to_payload(), "pid": os.getpid(),
        })
        if spec.test_startup_delay_seconds:
            time.sleep(spec.test_startup_delay_seconds)
        if spec.expected_runtime_digest is not None and (
            installed_core_release_digest() != spec.expected_runtime_digest
            or endpoint.release_digest != spec.expected_runtime_digest
        ):
            raise PermissionError("Core worker runtime release digest mismatch")
        engines = _engines(spec, connection)
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
            if kind != "respond" or set(message) != {
                "kind", "envelope", "payload", "role",
            }:
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
            role = message["role"]
            if role not in engines:
                raise PermissionError("Core worker model role is unavailable")
            try:
                if spec.test_delay_seconds:
                    time.sleep(spec.test_delay_seconds)
                response = engines[role].respond(decode_request(encoded))
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
    except BaseException as exc:
        if connection is not None:
            if isinstance(exc, PermissionError):
                code = "attestation_or_identity_rejected"
            elif isinstance(exc, (TypeError, ValueError)):
                code = "invalid_startup_contract"
            else:
                code = "child_startup_failed"
            try:
                _send(connection, {"kind": "startup_error", "code": code})
            except BaseException:
                pass
        return
    finally:
        if connection is not None:
            connection.close()
        lifetime_lock.release()


class _CoreWorkerProcess:
    def __init__(
        self, *, endpoint: ComponentEndpoint, spec: CoreEngineProcessSpec,
        runtime_dir: Path,
        providers: Mapping[str, PlatformProviderBinding] | None = None,
        startup_timeout: float = 60.0,
    ) -> None:
        self.endpoint = endpoint
        self.spec = spec
        self.runtime_dir = runtime_dir
        self.startup_timeout = startup_timeout
        if type(startup_timeout) not in {int, float} or not (
            1.0 <= startup_timeout <= 300.0
        ):
            raise ValueError("startup_timeout must be in 1..300 seconds")
        self.providers = dict(providers or {})
        expected_configurations = (
            {}
            if spec.kind != "provider"
            else {
                "primary": spec.provider,
                **(
                    {"secondary": spec.secondary_provider}
                    if spec.secondary_provider is not None else {}
                ),
            }
        )
        if set(self.providers) != set(expected_configurations):
            raise CoreWorkerError(
                "Core provider roles must have exact Platform bindings"
            )
        for role, configuration in expected_configurations.items():
            if self.providers[role].configuration != configuration:
                raise CoreWorkerError(
                    f"Core {role} provider binding configuration mismatch"
                )
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._listener: Listener | None = None
        # One worker owns one ordered IPC channel. Routing can ask primary and
        # secondary roles concurrently, while health supervision can sample at
        # the same time; serialize complete exchanges so replies cannot be
        # consumed by the wrong caller.
        self._ipc_lock = RLock()
        token = _endpoint_token(endpoint)
        # Linux AF_UNIX paths are commonly capped at 108 bytes. Keep the IPC
        # filename compact while retaining the full digest for durable locks.
        self._socket_path = runtime_dir / f"c-{token[:12]}.sock"
        self._lifetime_lock_path = runtime_dir / f"core-{token}.lifetime"
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
                  self.spec.to_payload(), str(self._lifetime_lock_path)),
            name=f"sofia-core-{self.endpoint.generation}", daemon=False,
        )
        self._process.start()
        deadline = time.monotonic() + self.startup_timeout
        while queue.empty() and self._process.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            thread.join(min(0.05, remaining))
        if queue.empty():
            exited = not self._process.is_alive()
            self.terminate(force=True)
            raise CoreWorkerError(
                "Core worker exited before authenticated IPC"
                if exited else "Core worker authenticated IPC deadline expired"
            )
        accepted = queue.get()
        if isinstance(accepted, BaseException):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker authenticated connection failed") from accepted
        self._connection = accepted
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._connection.poll(remaining):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker startup status deadline expired")
        starting = _receive(self._connection)
        expected_starting = {"kind", "protocol", "endpoint", "pid"}
        if set(starting) != expected_starting or starting["kind"] != "starting" or (
            starting["protocol"] != str(SDK_PROTOCOL_VERSION)
            or ComponentEndpoint.from_payload(starting["endpoint"]) != self.endpoint
            or starting["pid"] != self.pid
        ):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker startup identity mismatch")
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self._connection.poll(remaining):
            self.terminate(force=True)
            raise CoreWorkerError("Core worker attestation/readiness deadline expired")
        ready = _receive(self._connection)
        if ready.get("kind") == "startup_error" and set(ready) == {"kind", "code"}:
            code = ready["code"]
            self.terminate(force=True)
            raise CoreWorkerError(f"Core worker startup rejected: {code}")
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
        with self._ipc_lock:
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
        request: CognitiveRequest, timeout: float, role: str = "primary",
    ) -> CognitiveResponse:
        payload = encode_request(request)
        if sha256(payload).hexdigest() != envelope.payload_digest:
            raise ValueError("Core worker request envelope digest mismatch")
        if role not in {"primary", "secondary"}:
            raise ValueError("Core worker role must be primary or secondary")
        with self._ipc_lock:
            if self._connection is None or not self.alive:
                raise CoreWorkerError("Core worker is not connected")
            _send(self._connection, {
                "kind": "respond", "envelope": envelope.to_payload(),
                "payload": base64.b64encode(payload).decode("ascii"),
                "role": role,
            })
            deadline = time.monotonic() + timeout
            provider_calls = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._connection.poll(remaining):
                    raise TimeoutError("Core worker response deadline expired")
                value = _receive(self._connection)
                if value.get("kind") != "provider_request":
                    break
                provider_calls += 1
                if provider_calls > 1:
                    raise CoreWorkerError(
                        "Core worker exceeded bounded provider calls"
                    )
                self._serve_provider_request(
                    value=value, expected_role=role,
                )
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

    def _serve_provider_request(
        self, *, value: Mapping[str, object], expected_role: str,
    ) -> None:
        required = {
            "kind", "request_id", "role", "configuration_digest",
            "payload", "payload_digest",
        }
        if set(value) != required or value["role"] != expected_role:
            raise PermissionError("Core provider request role is incompatible")
        role = value["role"]
        if not isinstance(role, str) or role not in self.providers:
            raise PermissionError("Core provider role is unavailable")
        binding = self.providers[role]
        if value["configuration_digest"] != _configuration_digest(
            binding.configuration
        ):
            raise PermissionError("Core provider configuration identity mismatch")
        request_id = value["request_id"]
        if not isinstance(request_id, str) or not request_id.startswith("provider:"):
            raise PermissionError("Core provider request identity is invalid")
        try:
            payload = base64.b64decode(value["payload"], validate=True)
            if sha256(payload).hexdigest() != value["payload_digest"]:
                raise PermissionError("Core provider request digest mismatch")
            response = binding.provider.respond(decode_request(payload))
            result = encode_response(response)
            _send(self._connection, {
                "kind": "provider_response",
                "request_id": request_id,
                "configuration_digest": value["configuration_digest"],
                "payload": base64.b64encode(result).decode("ascii"),
                "payload_digest": sha256(result).hexdigest(),
            })
        except Exception:
            _send(self._connection, {
                "kind": "provider_error", "request_id": request_id,
            })

    def drain(self, timeout: float = 5.0) -> None:
        with self._ipc_lock:
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
        startup_timeout: timedelta = timedelta(seconds=60),
        providers: Mapping[str, PlatformProviderBinding] | None = None,
    ) -> None:
        self.generations = generations
        self.lease = lease
        self.platform_instance_id = platform_instance_id
        self.core_identity_id = core_identity_id
        self.component_id = component_id
        self.runtime_dir = runtime_dir
        self.response_timeout = response_timeout
        if not isinstance(startup_timeout, timedelta) or not (
            timedelta(seconds=1) <= startup_timeout <= timedelta(minutes=5)
        ):
            raise ValueError("startup_timeout must be in 1..300 seconds")
        self.startup_timeout = startup_timeout
        self.providers = dict(providers or {})
        if any(
            role not in {"primary", "secondary"}
            or not isinstance(binding, PlatformProviderBinding)
            for role, binding in self.providers.items()
        ):
            raise TypeError("providers must contain typed primary/secondary bindings")
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

    def bind_providers(
        self, providers: Mapping[str, PlatformProviderBinding],
    ) -> None:
        """Bind reviewed Platform providers before starting a generation."""
        if self._active is not None:
            raise RuntimeError("cannot change providers for an active Core generation")
        if self.providers:
            raise RuntimeError("Core provider bindings are already configured")
        candidate = dict(providers)
        if any(
            role not in {"primary", "secondary"}
            or not isinstance(binding, PlatformProviderBinding)
            for role, binding in candidate.items()
        ):
            raise TypeError("providers must contain typed primary/secondary bindings")
        self.providers = candidate

    def _stage(
        self, release_digest: str, spec: CoreEngineProcessSpec, now: datetime,
    ) -> _CoreWorkerProcess:
        expected = (
            {}
            if spec.kind != "provider"
            else {
                "primary": spec.provider,
                **(
                    {"secondary": spec.secondary_provider}
                    if spec.secondary_provider is not None else {}
                ),
            }
        )
        if set(self.providers) != set(expected) or any(
            self.providers[role].configuration != configuration
            for role, configuration in expected.items()
        ):
            raise CoreWorkerError(
                "Core engine specification lacks exact Platform provider bindings"
            )
        endpoint = self.generations.stage(
            component_id=self.component_id, kind=ComponentKind.CORE,
            release_digest=release_digest,
            platform_instance_id=self.platform_instance_id,
            core_identity_id=self.core_identity_id,
            lease=self.lease, now=now, reason="Core worker release staged",
        )
        return _CoreWorkerProcess(
            endpoint=endpoint, spec=spec, runtime_dir=self.runtime_dir,
            providers=self.providers,
            startup_timeout=self.startup_timeout.total_seconds(),
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

    def observe_prior_generation(self, endpoint: ComponentEndpoint) -> bool | None:
        """Use process-owned lifetime evidence without trusting a stale PID."""
        if not isinstance(endpoint, ComponentEndpoint):
            raise TypeError("endpoint must be ComponentEndpoint")
        path = self.runtime_dir / f"core-{_endpoint_token(endpoint)}.lifetime"
        return _ProcessLifetimeLock.observe_running(path)

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

    def authority_lost(self) -> None:
        """Stop admissions/effects when the lease cannot be renewed.

        The durable generation deliberately remains ACTIVE because an expired
        lease cannot truthfully mutate canonical state. A new owner must
        reconcile the lifetime lock before fencing it.
        """
        process = self._active
        if process is not None:
            process.terminate(force=True)
            self._active = None

    def respond(
        self, request: CognitiveRequest, *, role: str = "primary",
    ) -> CognitiveResponse:
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
                role=role,
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
    def __init__(
        self, controller: CoreWorkerController, *, role: str = "primary",
        configuration: ProviderConfiguration | None = None,
    ) -> None:
        if not isinstance(controller, CoreWorkerController):
            raise TypeError("controller must be CoreWorkerController")
        if role not in {"primary", "secondary"}:
            raise ValueError("Core worker role must be primary or secondary")
        if configuration is not None and not isinstance(
            configuration, ProviderConfiguration
        ):
            raise TypeError("configuration must be ProviderConfiguration or None")
        self.controller = controller
        self.role = role
        self.configuration = configuration

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        return self.controller.respond(request, role=self.role)


class CoreWorkerRuntimeBackend(ManagedRuntimeBackend):
    """Existing ComponentRuntimeSupervisor adapter for the Core process."""

    def __init__(
        self, *, controller: CoreWorkerController, release_digest: str,
        spec: CoreEngineProcessSpec,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(controller, CoreWorkerController):
            raise TypeError("controller must be CoreWorkerController")
        if (
            not isinstance(release_digest, str)
            or len(release_digest) != 64
            or any(character not in "0123456789abcdef" for character in release_digest)
        ):
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


class CoreWorkerProcessOwner:
    """Application-owned lease, supervisor and independently hosted Core.

    This owner uses a scoped row in the existing canonical RUN lease table.
    It does not create another scheduler or state authority.
    """

    def __init__(
        self, *, state_path: Path, release_digest: str,
        platform_instance_id: str, core_identity_id: str, component_id: str,
        runtime_dir: Path, spec: CoreEngineProcessSpec,
        providers: Mapping[str, PlatformProviderBinding] | None = None,
        lease_ttl_seconds: int = 180, response_timeout_seconds: int = 120,
        startup_timeout_seconds: int = 60,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing canonical state database required")
        if not isinstance(release_digest, str) or len(release_digest) != 64:
            raise ValueError("release_digest must be SHA-256")
        if type(lease_ttl_seconds) is not int or not 15 <= lease_ttl_seconds <= 300:
            raise ValueError("lease_ttl_seconds must be in 15..300")
        if type(response_timeout_seconds) is not int or not (
            1 <= response_timeout_seconds < lease_ttl_seconds
        ):
            raise ValueError("response timeout must be shorter than lease TTL")
        if type(startup_timeout_seconds) is not int or not (
            5 <= startup_timeout_seconds <= 300
        ):
            raise ValueError("startup timeout must be in 5..300 seconds")
        if startup_timeout_seconds >= lease_ttl_seconds:
            raise ValueError("startup timeout must be shorter than lease TTL")
        observed_digest = installed_core_release_digest()
        if observed_digest != release_digest:
            raise CoreWorkerError(
                "configured Core release digest does not match installed package"
            )
        if spec.expected_runtime_digest not in {None, release_digest}:
            raise CoreWorkerError("Core process specification release mismatch")
        spec = replace(spec, expected_runtime_digest=release_digest)
        self.clock = clock
        self.lease_ttl_seconds = lease_ttl_seconds
        self.lease_store = LocalRunLeaseStore(
            state_path, lease_key="component-core",
        )
        acquired = self.lease_store.acquire(
            owner_id=f"core-worker-owner:{uuid4().hex}", now=clock(),
            ttl_seconds=lease_ttl_seconds,
        )
        if acquired.lease is None:
            raise CoreWorkerError(
                f"Core worker RUN lease unavailable: {acquired.status}"
            )
        self.lease = acquired.lease
        try:
            self.generations = ComponentGenerationStore(
                state_path=state_path, lease_store=self.lease_store,
            )
            self.controller = CoreWorkerController(
                generations=self.generations, lease=self.lease,
                platform_instance_id=platform_instance_id,
                core_identity_id=core_identity_id, component_id=component_id,
                runtime_dir=runtime_dir,
                response_timeout=timedelta(seconds=response_timeout_seconds),
                startup_timeout=timedelta(seconds=startup_timeout_seconds),
                providers=providers,
            )
            self.supervisor = ComponentRuntimeSupervisor(
                state_path=state_path, lease_store=self.lease_store,
            )
            self.backend = CoreWorkerRuntimeBackend(
                controller=self.controller, release_digest=release_digest,
                spec=spec, clock=clock,
            )
            self.supervisor.register(
                ComponentSpec(component_id, SupervisedComponentKind.CORE),
                self.backend, now=clock(),
            )
        except Exception:
            self.lease_store.release(self.lease, now=clock())
            raise
        self._component_id = component_id
        self._stop = Event()
        self._renewal_error: str | None = None
        self._thread: Thread | None = None

    @classmethod
    def start(cls, **kwargs) -> "CoreWorkerProcessOwner":
        owner = cls(**kwargs)
        try:
            return owner.activate()
        except Exception:
            owner.close()
            raise

    def activate(self) -> "CoreWorkerProcessOwner":
        """Activate after any lease-bound dependencies have become ready."""
        if self._thread is not None or self.controller.endpoint is not None:
            raise RuntimeError("Core worker owner is already active")
        self.controller.reconcile_startup(
            observe_running=self.controller.observe_prior_generation,
            now=self.clock(),
        )
        action = self.supervisor.start_component(
            self._component_id, lease=self.lease, now=self.clock(),
        )
        if action.action not in {"started", "already_healthy"}:
            raise CoreWorkerError(
                f"Core worker supervisor refused startup: {action.action}"
            )
        health = self.controller.health()
        if not health.ready or not health.accepting:
            raise CoreWorkerError("Core worker did not pass authenticated readiness")
        self._thread = Thread(
            target=self._renew_loop, name="sofia-core-worker-lease",
            daemon=True,
        )
        self._thread.start()
        return self

    @property
    def renewal_error(self) -> str | None:
        return self._renewal_error

    def _renew_loop(self) -> None:
        interval = max(5.0, self.lease_ttl_seconds / 3)
        while not self._stop.wait(interval):
            try:
                result = self.lease_store.renew(
                    self.lease, now=self.clock(),
                    ttl_seconds=self.lease_ttl_seconds,
                )
                if result.lease is None:
                    raise CoreWorkerError(f"lease renewal failed: {result.status}")
                self.lease = result.lease
                self.controller.lease = result.lease
            except Exception as exc:
                self._renewal_error = type(exc).__name__
                self.controller.authority_lost()
                return

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=min(10.0, self.lease_ttl_seconds / 2))
        self._thread = None
        now = self.clock()
        if self.lease_store.holds(self.lease, now=now):
            try:
                self.supervisor.stop_component(
                    self._component_id, lease=self.lease, now=now,
                    reason="application shutdown",
                )
            finally:
                self.lease_store.release(self.lease, now=self.clock())
        else:
            self.controller.authority_lost()
