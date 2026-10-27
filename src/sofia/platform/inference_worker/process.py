"""Platform-owned isolated process for one exact inference provider role."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import base64
from hashlib import sha256
import hmac
import json
import multiprocessing
from multiprocessing.connection import Connection
import os
from pathlib import Path
import secrets
from threading import RLock
from threading import Event, Thread
from typing import Callable, Mapping
from uuid import uuid4

from sofia.core.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.core.cognition.provider import LLMProvider, LLMProviderError
from sofia.platform.cognition_provider import create_llm_provider
from sofia.platform.config.inference_endpoint import (
    configured_ollama_endpoint,
    validate_ollama_endpoint,
)
from sofia.platform.config.model import ProviderConfiguration
from sofia.platform.run.generation import ComponentGenerationStore, GenerationState
from sofia.platform.run.lease import LocalRunLeaseStore
from sofia.sdk import (
    ComponentEndpoint, ComponentKind, decode_request, decode_response,
    encode_request, encode_response,
)


PROTOCOL = "sofia.inference.worker.v1"
MAX_MESSAGE_BYTES = 1_400_000


class InferenceWorkerError(RuntimeError):
    pass


def _configuration_digest(
    configuration: ProviderConfiguration, endpoint: str,
) -> str:
    raw = json.dumps(
        {"provider": asdict(configuration), "endpoint": endpoint},
        sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def _canonical(value: Mapping[str, object]) -> bytes:
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("inference IPC payload must be canonical JSON") from exc
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("inference IPC payload exceeds size limit")
    return raw


def _send(connection: Connection, secret: bytes, body: Mapping[str, object]) -> None:
    encoded = _canonical(body)
    connection.send_bytes(_canonical({
        "body": body,
        "mac": hmac.new(secret, encoded, "sha256").hexdigest(),
    }))


def _receive(connection: Connection, secret: bytes) -> dict[str, object]:
    try:
        raw = connection.recv_bytes(MAX_MESSAGE_BYTES)
        value = json.loads(raw.decode("utf-8"))
    except (EOFError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InferenceWorkerError("inference IPC failed") from exc
    if not isinstance(value, dict) or set(value) != {"body", "mac"}:
        raise InferenceWorkerError("invalid inference IPC envelope")
    body, mac = value["body"], value["mac"]
    if not isinstance(body, dict) or not isinstance(mac, str) or not hmac.compare_digest(
        mac, hmac.new(secret, _canonical(body), "sha256").hexdigest(),
    ):
        raise InferenceWorkerError("inference IPC authentication failed")
    return body


@dataclass(frozen=True, slots=True)
class InferenceWorkerHealth:
    pid: int
    ready: bool
    accepting: bool
    role: str
    configuration_digest: str
    release_digest: str
    platform_instance_id: str
    epoch: int
    component_id: str
    generation: int


def _identity(
    *, configuration: ProviderConfiguration, role: str, release_digest: str,
    platform_instance_id: str, epoch: int, component_id: str,
    generation: int, endpoint: str,
) -> dict[str, object]:
    return {
        "role": role,
        "configuration_digest": _configuration_digest(configuration, endpoint),
        "release_digest": release_digest,
        "platform_instance_id": platform_instance_id,
        "epoch": epoch,
        "component_id": component_id,
        "generation": generation,
    }


def _worker_main(
    connection: Connection, secret: bytes,
    configuration_payload: dict[str, object], endpoint: str,
    identity: dict[str, object],
) -> None:
    try:
        configuration = ProviderConfiguration(**configuration_payload)
        endpoint = validate_ollama_endpoint(endpoint)
        expected = _identity(
            configuration=configuration,
            role=identity["role"],
            release_digest=identity["release_digest"],
            platform_instance_id=identity["platform_instance_id"],
            epoch=identity["epoch"],
            component_id=identity["component_id"],
            generation=identity["generation"],
            endpoint=endpoint,
        )
        if identity != expected:
            raise PermissionError("inference worker identity mismatch")
        from sofia.platform.core_worker.process import installed_core_release_digest
        if installed_core_release_digest() != identity["release_digest"]:
            raise PermissionError("inference worker runtime release mismatch")
        provider = create_llm_provider(configuration, endpoint=endpoint)
        pid = os.getpid()
        accepting = True
        _send(connection, secret, {
            "kind": "ready", "protocol": PROTOCOL, "pid": pid, **identity,
        })
        while True:
            message = _receive(connection, secret)
            kind = message.get("kind")
            if kind == "health" and set(message) == {"kind"}:
                _send(connection, secret, {
                    "kind": "health", "pid": pid, "ready": True,
                    "accepting": accepting, **identity,
                })
                continue
            if kind == "drain" and set(message) == {"kind"}:
                accepting = False
                _send(connection, secret, {"kind": "drained", "pid": pid})
                continue
            if kind == "shutdown" and set(message) == {"kind"}:
                _send(connection, secret, {"kind": "stopped", "pid": pid})
                return
            required = {
                "kind", "request_id", "configuration_digest", "payload",
                "payload_digest",
            }
            if kind != "respond" or set(message) != required or not accepting:
                raise PermissionError("unsupported or drained inference request")
            if message["configuration_digest"] != identity["configuration_digest"]:
                raise PermissionError("inference configuration identity mismatch")
            request_id = message["request_id"]
            try:
                payload = base64.b64decode(message["payload"], validate=True)
                if sha256(payload).hexdigest() != message["payload_digest"]:
                    raise PermissionError("inference request digest mismatch")
                result = encode_response(provider.respond(decode_request(payload)))
                _send(connection, secret, {
                    "kind": "response", "request_id": request_id,
                    "configuration_digest": identity["configuration_digest"],
                    "payload": base64.b64encode(result).decode("ascii"),
                    "payload_digest": sha256(result).hexdigest(),
                })
            except Exception as exc:
                _send(connection, secret, {
                    "kind": "provider_error", "request_id": request_id,
                    "error": type(exc).__name__,
                })
    except BaseException as exc:
        try:
            _send(connection, secret, {
                "kind": "worker_error", "error": type(exc).__name__,
            })
        except BaseException:
            pass
    finally:
        connection.close()


class InferenceProviderProcess(LLMProvider):
    """Provider proxy whose reviewed adapter runs in a distinct OS process."""

    def __init__(
        self, *, configuration: ProviderConfiguration, role: str,
        release_digest: str, platform_instance_id: str,
        endpoint: str | None = None,
        response_timeout_seconds: float = 120.0,
    ) -> None:
        if not isinstance(configuration, ProviderConfiguration):
            raise TypeError("configuration must be ProviderConfiguration")
        if role not in {"primary", "secondary"}:
            raise ValueError("inference role must be primary or secondary")
        if not isinstance(release_digest, str) or len(release_digest) != 64 or any(
            item not in "0123456789abcdef" for item in release_digest
        ):
            raise ValueError("release_digest must be SHA-256")
        if not isinstance(platform_instance_id, str) or not platform_instance_id:
            raise ValueError("platform_instance_id required")
        if type(response_timeout_seconds) not in {int, float} or not (
            0.1 <= response_timeout_seconds <= 300.0
        ):
            raise ValueError("response timeout must be in 0.1..300 seconds")
        self.configuration = configuration
        self.role = role
        self.release_digest = release_digest
        self.platform_instance_id = platform_instance_id
        self.endpoint = validate_ollama_endpoint(
            endpoint if endpoint is not None else configured_ollama_endpoint()
        )
        self.response_timeout_seconds = float(response_timeout_seconds)
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._secret: bytes | None = None
        self._identity: dict[str, object] | None = None
        self._lock = RLock()

    @property
    def pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    def start(
        self, *, endpoint: ComponentEndpoint, epoch: int,
    ) -> InferenceWorkerHealth:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("positive execution epoch required")
        if not isinstance(endpoint, ComponentEndpoint) or (
            endpoint.kind is not ComponentKind.INFERENCE
            or endpoint.release_digest != self.release_digest
            or endpoint.platform_instance_id != self.platform_instance_id
        ):
            raise ValueError("exact inference component endpoint required")
        if self._process is not None:
            raise RuntimeError("inference worker already started")
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        secret = secrets.token_bytes(32)
        identity = _identity(
            configuration=self.configuration, role=self.role,
            release_digest=self.release_digest,
            platform_instance_id=self.platform_instance_id, epoch=epoch,
            component_id=endpoint.component_id,
            generation=endpoint.generation,
            endpoint=self.endpoint,
        )
        process = context.Process(
            target=_worker_main,
            args=(
                child, secret, asdict(self.configuration), self.endpoint,
                identity,
            ),
            name=f"sofia-inference-{self.role}-{epoch}", daemon=False,
        )
        process.start()
        child.close()
        self._process, self._connection, self._secret, self._identity = (
            process, parent, secret, identity,
        )
        try:
            if not parent.poll(self.response_timeout_seconds):
                raise InferenceWorkerError("inference worker readiness deadline expired")
            ready = _receive(parent, secret)
            if ready != {
                "kind": "ready", "protocol": PROTOCOL,
                "pid": process.pid, **identity,
            }:
                raise InferenceWorkerError("inference worker readiness identity mismatch")
            return self.health()
        except Exception:
            self.close(force=True)
            raise

    def _rpc(self, body: Mapping[str, object]) -> dict[str, object]:
        with self._lock:
            process = self._process
            if process is None or not process.is_alive() or (
                self._connection is None or self._secret is None
            ):
                raise InferenceWorkerError("inference worker is unavailable")
            _send(self._connection, self._secret, body)
            if not self._connection.poll(self.response_timeout_seconds):
                self._terminate_locked()
                raise TimeoutError("inference worker response deadline expired")
            return _receive(self._connection, self._secret)

    def health(self) -> InferenceWorkerHealth:
        response = self._rpc({"kind": "health"})
        expected = self._identity
        if expected is None or response != {
            "kind": "health", "pid": self.pid, "ready": True,
            "accepting": True, **expected,
        }:
            raise InferenceWorkerError("inference worker health identity mismatch")
        return InferenceWorkerHealth(
            pid=response["pid"], ready=True, accepting=True,
            role=self.role,
            configuration_digest=response["configuration_digest"],
            release_digest=self.release_digest,
            platform_instance_id=self.platform_instance_id,
            epoch=response["epoch"],
            component_id=response["component_id"],
            generation=response["generation"],
        )

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        payload = encode_request(request)
        request_id = f"inference:{secrets.token_hex(16)}"
        response = self._rpc({
            "kind": "respond", "request_id": request_id,
            "configuration_digest": _configuration_digest(
                self.configuration, self.endpoint,
            ),
            "payload": base64.b64encode(payload).decode("ascii"),
            "payload_digest": sha256(payload).hexdigest(),
        })
        if response.get("kind") == "provider_error" and (
            response.get("request_id") == request_id
        ):
            raise LLMProviderError("isolated inference provider failed")
        if set(response) != {
            "kind", "request_id", "configuration_digest", "payload",
            "payload_digest",
        } or response["kind"] != "response" or (
            response["request_id"] != request_id
            or response["configuration_digest"] != _configuration_digest(
                self.configuration, self.endpoint,
            )
        ):
            raise InferenceWorkerError("inference response identity mismatch")
        result = base64.b64decode(response["payload"], validate=True)
        if sha256(result).hexdigest() != response["payload_digest"]:
            raise InferenceWorkerError("inference response digest mismatch")
        return decode_response(result)

    def _terminate_locked(self) -> None:
        process = self._process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(2.0)
        if process is not None and process.is_alive():
            process.kill()
            process.join(2.0)
        if self._connection is not None:
            self._connection.close()
        self._process = None
        self._connection = None
        self._secret = None
        self._identity = None

    def close(self, *, force: bool = False) -> bool:
        with self._lock:
            process = self._process
            if process is None:
                return True
            verified = False
            try:
                if not force and process.is_alive():
                    drained = self._rpc({"kind": "drain"})
                    if drained != {"kind": "drained", "pid": process.pid}:
                        raise InferenceWorkerError("inference drain identity mismatch")
                    stopped = self._rpc({"kind": "shutdown"})
                    if stopped != {"kind": "stopped", "pid": process.pid}:
                        raise InferenceWorkerError("inference stop identity mismatch")
                    verified = True
            finally:
                process.join(2.0)
                self._terminate_locked()
            return verified


class InferenceProcessOwner(LLMProvider):
    """Canonical RUN lease and generation owner for one provider process."""

    def __init__(
        self, *, state_path: Path, process: InferenceProviderProcess,
        component_id: str, lease_ttl_seconds: int = 180,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(state_path, Path) or not state_path.is_file():
            raise FileNotFoundError("existing canonical state database required")
        if not isinstance(process, InferenceProviderProcess):
            raise TypeError("process must be InferenceProviderProcess")
        if not isinstance(component_id, str) or not component_id.strip():
            raise ValueError("component_id required")
        if type(lease_ttl_seconds) is not int or not 15 <= lease_ttl_seconds <= 300:
            raise ValueError("lease_ttl_seconds must be in 15..300")
        self.process = process
        self.component_id = component_id
        self.clock = clock
        self.lease_ttl_seconds = lease_ttl_seconds
        self.lease_store = LocalRunLeaseStore(
            state_path, lease_key=f"component-{component_id}",
        )
        acquired = self.lease_store.acquire(
            owner_id=f"inference-owner:{uuid4().hex}", now=clock(),
            ttl_seconds=lease_ttl_seconds,
        )
        if acquired.lease is None:
            raise InferenceWorkerError(
                f"inference RUN lease unavailable: {acquired.status}"
            )
        self.lease = acquired.lease
        self.generations = ComponentGenerationStore(
            state_path=state_path, lease_store=self.lease_store,
        )
        self.endpoint: ComponentEndpoint | None = None
        self._stop = Event()
        self._thread: Thread | None = None
        self.renewal_error: str | None = None

    def start(self) -> InferenceWorkerHealth:
        if self.endpoint is not None:
            raise RuntimeError("inference process owner already started")
        if self.generations.active_for_component(self.component_id) is not None:
            self.lease_store.release(self.lease, now=self.clock())
            raise InferenceWorkerError(
                "prior inference generation requires explicit reconciliation"
            )
        endpoint = self.generations.stage(
            component_id=self.component_id, kind=ComponentKind.INFERENCE,
            release_digest=self.process.release_digest,
            platform_instance_id=self.process.platform_instance_id,
            core_identity_id=None, lease=self.lease, now=self.clock(),
            reason="inference provider process staged",
        )
        try:
            health = self.process.start(endpoint=endpoint, epoch=self.lease.epoch)
            if not health.ready or not health.accepting or (
                health.component_id != endpoint.component_id
                or health.generation != endpoint.generation
            ):
                raise InferenceWorkerError("inference readiness identity mismatch")
            self.generations.activate(
                endpoint, lease=self.lease, now=self.clock(),
                reason="authenticated inference readiness verified",
            )
        except Exception:
            self.process.close(force=True)
            self.generations.quarantine_staged(
                endpoint, lease=self.lease, now=self.clock(),
                reason="inference process failed readiness",
            )
            self.lease_store.release(self.lease, now=self.clock())
            raise
        self.endpoint = endpoint
        self._thread = Thread(
            target=self._renew_loop,
            name=f"sofia-inference-lease-{self.process.role}", daemon=True,
        )
        self._thread.start()
        return health

    def _renew_loop(self) -> None:
        interval = max(5.0, self.lease_ttl_seconds / 3)
        while not self._stop.wait(interval):
            try:
                result = self.lease_store.renew(
                    self.lease, now=self.clock(),
                    ttl_seconds=self.lease_ttl_seconds,
                )
                if result.lease is None:
                    raise InferenceWorkerError(
                        f"inference lease renewal failed: {result.status}"
                    )
                self.lease = result.lease
            except Exception as exc:
                self.renewal_error = type(exc).__name__
                self.process.close(force=True)
                return

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        endpoint = self.endpoint
        now = self.clock()
        current = self.lease_store.current(now=now)
        if endpoint is None or not self.generations.is_active(endpoint) or (
            current is None or current.owner_id != self.lease.owner_id
            or current.epoch != self.lease.epoch
        ):
            raise LLMProviderError("inference generation authority is unavailable")
        return self.process.respond(request)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def health(self) -> InferenceWorkerHealth:
        if self.endpoint is None or not self.generations.is_active(self.endpoint):
            raise InferenceWorkerError("inference generation is not active")
        return self.process.health()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=min(10.0, self.lease_ttl_seconds / 2))
        self._thread = None
        endpoint = self.endpoint
        now = self.clock()
        if self.lease_store.holds(self.lease, now=now):
            try:
                if endpoint is not None and self.generations.is_active(endpoint):
                    self.generations.begin_drain(
                        endpoint, lease=self.lease, now=now,
                        reason="inference provider shutdown",
                    )
                    verified = self.process.close()
                    self.generations.fence(
                        endpoint, lease=self.lease, now=self.clock(),
                        reason=(
                            "inference process exit verified"
                            if verified else "inference process exit uncertain"
                        ),
                        quarantine=not verified,
                    )
                elif endpoint is not None and self.generations.state(
                    endpoint
                ) is GenerationState.DRAINING:
                    self.process.close(force=True)
                    self.generations.fence(
                        endpoint, lease=self.lease, now=self.clock(),
                        reason="inference process fenced after external drain",
                        quarantine=True,
                    )
                else:
                    self.process.close(force=True)
            finally:
                self.lease_store.release(self.lease, now=self.clock())
        else:
            self.process.close(force=True)
        self.endpoint = None


class InferenceProcessGroup:
    """Ordered owner for exact provider-role processes."""

    def __init__(self, providers: Mapping[str, InferenceProcessOwner]) -> None:
        self.providers = dict(providers)

    def close(self) -> None:
        failure: Exception | None = None
        for provider in reversed(tuple(self.providers.values())):
            try:
                provider.close()
            except Exception as exc:
                if failure is None:
                    failure = exc
        if failure is not None:
            raise failure
