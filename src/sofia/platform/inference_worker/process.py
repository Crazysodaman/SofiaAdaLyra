"""Platform-owned isolated process for one exact inference provider role."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import base64
from hashlib import sha256
import hmac
import json
import multiprocessing
from multiprocessing.connection import Connection
import os
import secrets
from threading import RLock
from typing import Mapping

from sofia.core.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.core.cognition.provider import LLMProvider, LLMProviderError
from sofia.platform.cognition_provider import create_llm_provider
from sofia.platform.config.model import ProviderConfiguration
from sofia.sdk import decode_request, decode_response, encode_request, encode_response


PROTOCOL = "sofia.inference.worker.v1"
MAX_MESSAGE_BYTES = 1_400_000


class InferenceWorkerError(RuntimeError):
    pass


def _configuration_digest(configuration: ProviderConfiguration) -> str:
    raw = json.dumps(
        asdict(configuration), sort_keys=True, separators=(",", ":"),
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


def _identity(
    *, configuration: ProviderConfiguration, role: str, release_digest: str,
    platform_instance_id: str, epoch: int,
) -> dict[str, object]:
    return {
        "role": role,
        "configuration_digest": _configuration_digest(configuration),
        "release_digest": release_digest,
        "platform_instance_id": platform_instance_id,
        "epoch": epoch,
    }


def _worker_main(
    connection: Connection, secret: bytes,
    configuration_payload: dict[str, object], identity: dict[str, object],
) -> None:
    try:
        configuration = ProviderConfiguration(**configuration_payload)
        expected = _identity(
            configuration=configuration,
            role=identity["role"],
            release_digest=identity["release_digest"],
            platform_instance_id=identity["platform_instance_id"],
            epoch=identity["epoch"],
        )
        if identity != expected:
            raise PermissionError("inference worker identity mismatch")
        from sofia.platform.core_worker.process import installed_core_release_digest
        if installed_core_release_digest() != identity["release_digest"]:
            raise PermissionError("inference worker runtime release mismatch")
        provider = create_llm_provider(configuration)
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
        self.response_timeout_seconds = float(response_timeout_seconds)
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._secret: bytes | None = None
        self._identity: dict[str, object] | None = None
        self._lock = RLock()

    @property
    def pid(self) -> int | None:
        return None if self._process is None else self._process.pid

    def start(self, *, epoch: int) -> InferenceWorkerHealth:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("positive execution epoch required")
        if self._process is not None:
            raise RuntimeError("inference worker already started")
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        secret = secrets.token_bytes(32)
        identity = _identity(
            configuration=self.configuration, role=self.role,
            release_digest=self.release_digest,
            platform_instance_id=self.platform_instance_id, epoch=epoch,
        )
        process = context.Process(
            target=_worker_main,
            args=(child, secret, asdict(self.configuration), identity),
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
        )

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        payload = encode_request(request)
        request_id = f"inference:{secrets.token_hex(16)}"
        response = self._rpc({
            "kind": "respond", "request_id": request_id,
            "configuration_digest": _configuration_digest(self.configuration),
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
                self.configuration
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

    def close(self, *, force: bool = False) -> None:
        with self._lock:
            process = self._process
            if process is None:
                return
            try:
                if not force and process.is_alive():
                    drained = self._rpc({"kind": "drain"})
                    if drained != {"kind": "drained", "pid": process.pid}:
                        raise InferenceWorkerError("inference drain identity mismatch")
                    stopped = self._rpc({"kind": "shutdown"})
                    if stopped != {"kind": "stopped", "pid": process.pid}:
                        raise InferenceWorkerError("inference stop identity mismatch")
            finally:
                process.join(2.0)
                self._terminate_locked()


class InferenceProcessGroup:
    """Ordered owner for exact provider-role processes."""

    def __init__(self, providers: Mapping[str, InferenceProviderProcess]) -> None:
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
