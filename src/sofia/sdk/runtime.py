"""Portable, authority-free Core runtime facade.

This module defines the public contract an independently packaged Core worker
may implement without importing ``sofia.core``, ``sofia.application`` or any
privileged Platform module.  It adds a strict JSON-lines request/response
protocol and a small dispatcher for hello negotiation, lifecycle, bounded chat
and task requests, history and health.

The existing component wire protocol remains exactly ``1.0``.  Nothing in this
module authenticates a peer, grants a capability, writes Platform state or
claims that a requested effect occurred.  A response is a report from the
worker; verified Platform receipts remain a separate authority boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import re
from typing import BinaryIO, Mapping, Protocol, runtime_checkable

from .contract_wire import (
    MAX_MESSAGE_BYTES,
    ContractWireError,
    canonical_json_bytes,
    loads_strict,
)
from .contracts import ProtocolVersion, SDK_PROTOCOL_VERSION


RUNTIME_SCHEMA = "aegis.core.runtime.v1"
RUNTIME_PROTOCOL_VERSION = SDK_PROTOCOL_VERSION
MAX_RUNTIME_MESSAGE_BYTES = MAX_MESSAGE_BYTES
MAX_RUNTIME_PAYLOAD_BYTES = 48 * 1024
MAX_RUNTIME_TEXT_CHARS = 4000
MAX_RUNTIME_DETAIL_CHARS = 512
MAX_RUNTIME_IDEMPOTENCY_RECORDS = 1024
UNKNOWN_REQUEST_ID = "unknown-request"
UNKNOWN_IDEMPOTENCY_KEY = "unknown-idempotency"

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_REQUEST_FIELDS = frozenset({
    "protocol",
    "request_id",
    "idempotency_key",
    "operation",
    "deadline",
    "payload",
})
_RESPONSE_FIELDS = frozenset({
    "protocol",
    "request_id",
    "idempotency_key",
    "outcome",
    "code",
    "detail",
    "payload",
    "completed_at",
})


class RuntimeProtocolError(ValueError):
    """Stable, language-neutral rejection of a runtime message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RuntimeOperation(str, Enum):
    HELLO = "hello"
    START = "start"
    CHAT = "chat"
    TASK = "task"
    HISTORY = "history"
    HEALTH = "health"
    STOP = "stop"


class RuntimeOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"
    UNAVAILABLE = "unavailable"


class RuntimeAdapterError(Exception):
    """Adapter rejection carrying an explicit portable outcome."""

    outcome = RuntimeOutcome.FAILED

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class RuntimeDenied(RuntimeAdapterError):
    outcome = RuntimeOutcome.DENIED


class RuntimeFailed(RuntimeAdapterError):
    outcome = RuntimeOutcome.FAILED


class RuntimeUnavailable(RuntimeAdapterError):
    outcome = RuntimeOutcome.UNAVAILABLE


class RuntimeOutcomeUnknown(RuntimeAdapterError):
    outcome = RuntimeOutcome.OUTCOME_UNKNOWN


class RuntimeCancelled(RuntimeAdapterError):
    outcome = RuntimeOutcome.FAILED

    def __init__(self, detail: str = "task was cancelled") -> None:
        super().__init__("cancelled", detail)


def _utc(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise RuntimeProtocolError("invalid_deadline", f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise RuntimeProtocolError(
            "invalid_request", f"{label} must be a bounded identifier"
        )
    return value


def _exact(document: object, fields: frozenset[str], label: str) -> Mapping[str, object]:
    if not isinstance(document, Mapping):
        raise RuntimeProtocolError("invalid_request", f"{label} must be a JSON object")
    keys = set(document)
    if keys != fields:
        if keys - fields:
            raise RuntimeProtocolError(
                "unknown_field", f"{label} contains unexpected fields"
            )
        raise RuntimeProtocolError(
            "missing_field", f"{label} is missing required fields"
        )
    return document


def _bounded_detail(detail: object) -> str:
    if not isinstance(detail, str) or len(detail) > MAX_RUNTIME_DETAIL_CHARS:
        raise RuntimeProtocolError(
            "invalid_detail", "detail must be bounded text"
        )
    return detail


def _code(value: object, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise RuntimeProtocolError(
                "invalid_outcome", "non-success outcome requires a code"
            )
        return None
    if not isinstance(value, str) or _CODE.fullmatch(value) is None:
        raise RuntimeProtocolError("invalid_code", "code must be a bounded token")
    return value


def _bounded_payload(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) for key in value
    ):
        raise RuntimeProtocolError(
            "invalid_payload", "payload must be a string-keyed object"
        )
    payload = dict(value)
    try:
        encoded = canonical_json_bytes(payload)
    except ContractWireError as exc:
        raise RuntimeProtocolError("invalid_payload", "payload is not canonical JSON") from exc
    if len(encoded) > MAX_RUNTIME_PAYLOAD_BYTES:
        raise RuntimeProtocolError(
            "payload_too_large", "payload exceeds the runtime bound"
        )
    return payload


def _validate_operation_payload(
    operation: RuntimeOperation, payload: Mapping[str, object]
) -> None:
    fields = set(payload)
    if operation is RuntimeOperation.CHAT:
        if fields != {"text"}:
            code = "unknown_field" if fields - {"text"} else "missing_field"
            raise RuntimeProtocolError(code, "chat payload requires exactly text")
        text = payload["text"]
        if not isinstance(text, str):
            raise RuntimeProtocolError("invalid_text", "text must be a string")
        if len(text) > MAX_RUNTIME_TEXT_CHARS:
            raise RuntimeProtocolError(
                "text_too_large", "text exceeds the runtime character bound"
            )
        return
    if operation is RuntimeOperation.TASK:
        if fields != {"task", "arguments"}:
            code = "unknown_field" if fields - {"task", "arguments"} else "missing_field"
            raise RuntimeProtocolError(
                code, "task payload requires exactly task and arguments"
            )
        name = payload["task"]
        if not isinstance(name, str) or _ID.fullmatch(name) is None:
            raise RuntimeProtocolError(
                "invalid_task_name", "task must be a bounded identifier"
            )
        arguments = payload["arguments"]
        if not isinstance(arguments, Mapping) or any(
            not isinstance(key, str) for key in arguments
        ):
            raise RuntimeProtocolError(
                "invalid_arguments", "task arguments must be a string-keyed object"
            )
        try:
            encoded = canonical_json_bytes(dict(arguments))
        except ContractWireError as exc:
            raise RuntimeProtocolError(
                "invalid_arguments", "task arguments are not canonical JSON"
            ) from exc
        if len(encoded) > MAX_RUNTIME_PAYLOAD_BYTES:
            raise RuntimeProtocolError(
                "payload_too_large", "task arguments exceed the runtime bound"
            )
        return
    if fields:
        raise RuntimeProtocolError(
            "unknown_field", f"{operation.value} payload must be empty"
        )


@dataclass(frozen=True, slots=True)
class RuntimeRequest:
    protocol: ProtocolVersion
    request_id: str
    idempotency_key: str
    operation: RuntimeOperation
    deadline: datetime
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, ProtocolVersion):
            raise RuntimeProtocolError("invalid_protocol", "protocol must be typed")
        if self.protocol != RUNTIME_PROTOCOL_VERSION:
            raise RuntimeProtocolError(
                "unsupported_protocol", "runtime protocol version is unsupported"
            )
        _identifier(self.request_id, "request_id")
        _identifier(self.idempotency_key, "idempotency_key")
        if not isinstance(self.operation, RuntimeOperation):
            raise RuntimeProtocolError("unknown_op", "operation is unsupported")
        object.__setattr__(self, "deadline", _utc(self.deadline, "deadline"))
        payload = _bounded_payload(self.payload)
        _validate_operation_payload(self.operation, payload)
        object.__setattr__(self, "payload", payload)

    def fingerprint(self) -> str:
        return sha256(canonical_json_bytes({
            "operation": self.operation.value,
            "payload": dict(self.payload),
            "protocol": str(self.protocol),
        })).hexdigest()

    def to_payload(self) -> dict[str, object]:
        return {
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "operation": self.operation.value,
            "deadline": self.deadline.isoformat(),
            "payload": dict(self.payload),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "RuntimeRequest":
        document = _exact(payload, _REQUEST_FIELDS, "runtime request")
        try:
            raw_protocol = document["protocol"]
            if not isinstance(raw_protocol, str):
                raise RuntimeProtocolError(
                    "malformed_protocol", "protocol must use MAJOR.MINOR"
                )
            try:
                operation = RuntimeOperation(document["operation"])
            except (TypeError, ValueError) as exc:
                raise RuntimeProtocolError(
                    "unknown_op", "operation is unsupported"
                ) from exc
            deadline = datetime.fromisoformat(document["deadline"])  # type: ignore[arg-type]
            return cls(
                protocol=ProtocolVersion.parse(raw_protocol),
                request_id=document["request_id"],  # type: ignore[arg-type]
                idempotency_key=document["idempotency_key"],  # type: ignore[arg-type]
                operation=operation,
                deadline=deadline,
                payload=document["payload"],  # type: ignore[arg-type]
            )
        except RuntimeProtocolError:
            raise
        except (TypeError, ValueError) as exc:
            raise RuntimeProtocolError(
                "invalid_request", "runtime request is invalid"
            ) from exc


@dataclass(frozen=True, slots=True)
class RuntimeResponse:
    protocol: ProtocolVersion
    request_id: str
    idempotency_key: str
    outcome: RuntimeOutcome
    code: str | None
    detail: str
    payload: Mapping[str, object]
    completed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, ProtocolVersion):
            raise RuntimeProtocolError("invalid_protocol", "protocol must be typed")
        if self.protocol != RUNTIME_PROTOCOL_VERSION:
            raise RuntimeProtocolError(
                "unsupported_protocol", "runtime protocol version is unsupported"
            )
        _identifier(self.request_id, "request_id")
        _identifier(self.idempotency_key, "idempotency_key")
        if not isinstance(self.outcome, RuntimeOutcome):
            raise RuntimeProtocolError("invalid_outcome", "outcome must be typed")
        _code(self.code, required=self.outcome is not RuntimeOutcome.SUCCEEDED)
        detail = _bounded_detail(self.detail)
        if self.outcome is RuntimeOutcome.SUCCEEDED and self.code is not None:
            raise RuntimeProtocolError(
                "invalid_outcome", "successful outcome must not carry a code"
            )
        object.__setattr__(self, "detail", detail)
        object.__setattr__(self, "payload", _bounded_payload(self.payload))
        object.__setattr__(
            self, "completed_at", _utc(self.completed_at, "completed_at")
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "protocol": str(self.protocol),
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "outcome": self.outcome.value,
            "code": self.code,
            "detail": self.detail,
            "payload": dict(self.payload),
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: object) -> "RuntimeResponse":
        document = _exact(payload, _RESPONSE_FIELDS, "runtime response")
        try:
            raw_protocol = document["protocol"]
            if not isinstance(raw_protocol, str):
                raise RuntimeProtocolError(
                    "malformed_protocol", "protocol must use MAJOR.MINOR"
                )
            completed_at = datetime.fromisoformat(  # type: ignore[arg-type]
                document["completed_at"]
            )
            return cls(
                protocol=ProtocolVersion.parse(raw_protocol),
                request_id=document["request_id"],  # type: ignore[arg-type]
                idempotency_key=document["idempotency_key"],  # type: ignore[arg-type]
                outcome=RuntimeOutcome(document["outcome"]),
                code=document["code"],  # type: ignore[arg-type]
                detail=document["detail"],  # type: ignore[arg-type]
                payload=document["payload"],  # type: ignore[arg-type]
                completed_at=completed_at,
            )
        except RuntimeProtocolError:
            raise
        except (TypeError, ValueError) as exc:
            raise RuntimeProtocolError(
                "invalid_response", "runtime response is invalid"
            ) from exc


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    """Adapter-owned result before the dispatcher adds request correlation."""

    outcome: RuntimeOutcome
    code: str | None = None
    detail: str = ""
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, RuntimeOutcome):
            raise RuntimeProtocolError("invalid_outcome", "outcome must be typed")
        _code(self.code, required=self.outcome is not RuntimeOutcome.SUCCEEDED)
        object.__setattr__(self, "detail", _bounded_detail(self.detail))
        object.__setattr__(self, "payload", _bounded_payload(self.payload))

    @classmethod
    def succeeded(
        cls, payload: Mapping[str, object] | None = None, detail: str = ""
    ) -> "RuntimeResult":
        return cls(RuntimeOutcome.SUCCEEDED, None, detail, payload or {})

    @classmethod
    def denied(cls, code: str, detail: str = "") -> "RuntimeResult":
        return cls(RuntimeOutcome.DENIED, code, detail)

    @classmethod
    def failed(cls, code: str, detail: str = "") -> "RuntimeResult":
        return cls(RuntimeOutcome.FAILED, code, detail)

    @classmethod
    def outcome_unknown(cls, code: str, detail: str = "") -> "RuntimeResult":
        return cls(RuntimeOutcome.OUTCOME_UNKNOWN, code, detail)

    @classmethod
    def unavailable(cls, code: str, detail: str = "") -> "RuntimeResult":
        return cls(RuntimeOutcome.UNAVAILABLE, code, detail)


@runtime_checkable
class CoreRuntimeAdapter(Protocol):
    """Portable worker contract; constructing one grants no authority."""

    def hello(self, request: RuntimeRequest) -> RuntimeResult: ...

    def start(self, request: RuntimeRequest) -> RuntimeResult: ...

    def chat(self, request: RuntimeRequest) -> RuntimeResult: ...

    def task(self, request: RuntimeRequest) -> RuntimeResult: ...

    def history(self, request: RuntimeRequest) -> RuntimeResult: ...

    def health(self, request: RuntimeRequest) -> RuntimeResult: ...

    def stop(self, request: RuntimeRequest) -> RuntimeResult: ...


def _coerce_version(value: object) -> ProtocolVersion:
    if isinstance(value, ProtocolVersion):
        return value
    if isinstance(value, str):
        try:
            return ProtocolVersion.parse(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeProtocolError(
                "malformed_protocol", "protocol must use MAJOR.MINOR"
            ) from exc
    if (
        type(value) is tuple
        and len(value) == 2
        and all(type(part) is int for part in value)
    ):
        try:
            return ProtocolVersion(value[0], value[1])
        except ValueError as exc:
            raise RuntimeProtocolError(
                "malformed_protocol", "protocol is out of range"
            ) from exc
    raise RuntimeProtocolError(
        "malformed_protocol", "protocol must be a version string or pair"
    )


def negotiate_runtime_protocol(peer: object) -> ProtocolVersion:
    """Return the exact supported runtime version or fail closed."""
    version = _coerce_version(peer)
    if version != RUNTIME_PROTOCOL_VERSION:
        raise RuntimeProtocolError(
            "unsupported_protocol", "runtime protocol version is unsupported"
        )
    return RUNTIME_PROTOCOL_VERSION


def _wire_error(exc: ContractWireError) -> RuntimeProtocolError:
    code = exc.code
    if code == "oversized":
        code = "message_too_large"
    elif code == "malformed_json":
        code = "invalid_json"
    return RuntimeProtocolError(code, str(exc))


def _decode_document(raw: bytes) -> object:
    if not isinstance(raw, bytes):
        raise TypeError("runtime message must be bytes")
    if len(raw) > MAX_RUNTIME_MESSAGE_BYTES:
        raise RuntimeProtocolError(
            "message_too_large", "runtime message exceeds the byte limit"
        )
    try:
        return loads_strict(raw)
    except ContractWireError as exc:
        raise _wire_error(exc) from exc


def decode_request(raw: bytes) -> RuntimeRequest:
    document = _decode_document(raw)
    return RuntimeRequest.from_payload(document)


def decode_response(raw: bytes) -> RuntimeResponse:
    document = _decode_document(raw)
    return RuntimeResponse.from_payload(document)


def encode_request(request: RuntimeRequest) -> bytes:
    if not isinstance(request, RuntimeRequest):
        raise TypeError("request must be RuntimeRequest")
    try:
        raw = canonical_json_bytes(request.to_payload())
    except ContractWireError as exc:
        raise _wire_error(exc) from exc
    if len(raw) > MAX_RUNTIME_MESSAGE_BYTES:
        raise RuntimeProtocolError(
            "message_too_large", "runtime request exceeds the byte limit"
        )
    return raw


def encode_response(response: RuntimeResponse) -> bytes:
    if not isinstance(response, RuntimeResponse):
        raise TypeError("response must be RuntimeResponse")
    try:
        raw = canonical_json_bytes(response.to_payload())
    except ContractWireError as exc:
        raise _wire_error(exc) from exc
    if len(raw) > MAX_RUNTIME_MESSAGE_BYTES:
        raise RuntimeProtocolError(
            "message_too_large", "runtime response exceeds the byte limit"
        )
    return raw


def encode_request_line(request: RuntimeRequest) -> bytes:
    return encode_request(request) + b"\n"


def encode_response_line(response: RuntimeResponse) -> bytes:
    return encode_response(response) + b"\n"


def read_message_line(
    stream: BinaryIO, max_bytes: int = MAX_RUNTIME_MESSAGE_BYTES
) -> bytes | None:
    """Read one bounded line, returning ``None`` at EOF and ``b""`` if empty."""
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    raw = stream.readline(max_bytes + 2)
    if raw == b"":
        return None
    if not isinstance(raw, bytes):
        raise TypeError("runtime stream must be binary")
    ended = raw.endswith(b"\n")
    content = raw[:-1] if ended else raw
    if len(content) > max_bytes:
        if not ended:
            while True:
                remainder = stream.readline(max_bytes + 2)
                if not remainder or remainder.endswith(b"\n"):
                    break
        raise RuntimeProtocolError(
            "message_too_large", "runtime message exceeds the byte limit"
        )
    return content


_REJECTION_CODES = frozenset({
    "duplicate_key",
    "duplicate_request_id",
    "idempotency_conflict",
    "invalid_arguments",
    "invalid_code",
    "invalid_deadline",
    "invalid_detail",
    "invalid_outcome",
    "invalid_payload",
    "invalid_protocol",
    "invalid_request",
    "invalid_response",
    "invalid_task_name",
    "invalid_text",
    "message_too_large",
    "missing_field",
    "payload_too_large",
    "text_too_large",
    "unknown_field",
    "unknown_op",
    "unsupported_protocol",
})


def _error_outcome(code: str) -> RuntimeOutcome:
    return (
        RuntimeOutcome.DENIED
        if code in _REJECTION_CODES
        else RuntimeOutcome.FAILED
    )


def runtime_error_response(
    error: RuntimeProtocolError, *, now: datetime | None = None
) -> RuntimeResponse:
    code = error.code if _CODE.fullmatch(error.code) else "invalid_request"
    detail = str(error)
    if len(detail) > MAX_RUNTIME_DETAIL_CHARS:
        detail = detail[:MAX_RUNTIME_DETAIL_CHARS]
    moment = _utc(now or datetime.now(timezone.utc), "now")
    return RuntimeResponse(
        protocol=RUNTIME_PROTOCOL_VERSION,
        request_id=UNKNOWN_REQUEST_ID,
        idempotency_key=UNKNOWN_IDEMPOTENCY_KEY,
        outcome=_error_outcome(code),
        code=code,
        detail=detail,
        payload={},
        completed_at=moment,
    )


class RuntimeDispatcher:
    """Validate, deduplicate and dispatch portable runtime requests."""

    def __init__(
        self,
        adapter: CoreRuntimeAdapter,
        *,
        idempotency_limit: int = MAX_RUNTIME_IDEMPOTENCY_RECORDS,
    ) -> None:
        if type(idempotency_limit) is not int or idempotency_limit < 1:
            raise ValueError("idempotency_limit must be positive")
        if not isinstance(adapter, CoreRuntimeAdapter):
            raise TypeError("adapter does not implement CoreRuntimeAdapter")
        self._adapter = adapter
        self._limit = idempotency_limit
        self._idempotency: dict[str, tuple[str, RuntimeResult]] = {}
        self._request_ids: dict[str, str] = {}

    def _remember_request_id(self, request_id: str, idempotency_key: str) -> None:
        self._request_ids[request_id] = idempotency_key
        while len(self._request_ids) > self._limit:
            self._request_ids.pop(next(iter(self._request_ids)), None)

    def _remember(
        self, request: RuntimeRequest, fingerprint: str, result: RuntimeResult
    ) -> None:
        if (
            request.idempotency_key not in self._idempotency
            and len(self._idempotency) >= self._limit
        ):
            oldest = next(iter(self._idempotency), None)
            if oldest is not None:
                self._idempotency.pop(oldest, None)
        self._idempotency[request.idempotency_key] = (fingerprint, result)
        self._remember_request_id(request.request_id, request.idempotency_key)

    def _response(
        self, request: RuntimeRequest, result: RuntimeResult, moment: datetime
    ) -> RuntimeResponse:
        return RuntimeResponse(
            protocol=RUNTIME_PROTOCOL_VERSION,
            request_id=request.request_id,
            idempotency_key=request.idempotency_key,
            outcome=result.outcome,
            code=result.code,
            detail=result.detail,
            payload=result.payload,
            completed_at=moment,
        )

    def _invoke(self, request: RuntimeRequest) -> RuntimeResult:
        method = getattr(self._adapter, request.operation.value)
        return method(request)

    def dispatch(
        self, request: RuntimeRequest, *, now: datetime | None = None
    ) -> RuntimeResponse:
        if not isinstance(request, RuntimeRequest):
            raise TypeError("request must be RuntimeRequest")
        moment = _utc(now or datetime.now(timezone.utc), "now")
        known = self._request_ids.get(request.request_id)
        if known is not None and known != request.idempotency_key:
            return self._response(
                request,
                RuntimeResult.denied(
                    "duplicate_request_id",
                    "request_id was already used with another idempotency key",
                ),
                moment,
            )
        fingerprint = request.fingerprint()
        cached = self._idempotency.get(request.idempotency_key)
        if cached is not None:
            cached_fingerprint, cached_result = cached
            if cached_fingerprint != fingerprint:
                return self._response(
                    request,
                    RuntimeResult.denied(
                        "idempotency_conflict",
                        "idempotency_key was already used for a different request",
                    ),
                    moment,
                )
            self._remember_request_id(
                request.request_id, request.idempotency_key
            )
            return self._response(request, cached_result, moment)
        if moment >= request.deadline:
            return self._response(
                request,
                RuntimeResult.failed(
                    "deadline_exceeded", "request deadline has expired"
                ),
                moment,
            )
        try:
            result = self._invoke(request)
        except RuntimeAdapterError as exc:
            result = RuntimeResult(exc.outcome, exc.code, exc.detail)
        except Exception:
            result = RuntimeResult(
                RuntimeOutcome.OUTCOME_UNKNOWN,
                "internal_error",
                "adapter raised an unexpected exception",
            )
        if not isinstance(result, RuntimeResult):
            result = RuntimeResult(
                RuntimeOutcome.OUTCOME_UNKNOWN,
                "invalid_adapter_result",
                "adapter did not return a RuntimeResult",
            )
        self._remember(request, fingerprint, result)
        return self._response(request, result, moment)

    def handle_line(
        self, raw: bytes, *, now: datetime | None = None
    ) -> bytes:
        try:
            request = decode_request(raw)
        except RuntimeProtocolError as exc:
            return encode_response_line(runtime_error_response(exc, now=now))
        return encode_response_line(self.dispatch(request, now=now))


def serve(
    adapter: CoreRuntimeAdapter,
    stdin: BinaryIO,
    stdout: BinaryIO,
    *,
    max_line_bytes: int = MAX_RUNTIME_MESSAGE_BYTES,
    now: datetime | None = None,
) -> int:
    """Serve strict JSON-lines requests until stop or EOF."""
    dispatcher = RuntimeDispatcher(adapter)
    while True:
        try:
            content = read_message_line(stdin, max_line_bytes)
        except RuntimeProtocolError as exc:
            stdout.write(
                encode_response_line(runtime_error_response(exc, now=now))
            )
            stdout.flush()
            continue
        if content is None:
            return 0
        try:
            request = decode_request(content)
        except RuntimeProtocolError as exc:
            stdout.write(
                encode_response_line(runtime_error_response(exc, now=now))
            )
            stdout.flush()
            continue
        response = dispatcher.dispatch(request, now=now)
        try:
            line = encode_response_line(response)
        except RuntimeProtocolError as exc:
            line = encode_response_line(runtime_error_response(exc, now=now))
        stdout.write(line)
        stdout.flush()
        if (
            request.operation is RuntimeOperation.STOP
            and response.outcome is RuntimeOutcome.SUCCEEDED
        ):
            return 0


__all__ = [
    "CoreRuntimeAdapter",
    "MAX_RUNTIME_DETAIL_CHARS",
    "MAX_RUNTIME_IDEMPOTENCY_RECORDS",
    "MAX_RUNTIME_MESSAGE_BYTES",
    "MAX_RUNTIME_PAYLOAD_BYTES",
    "MAX_RUNTIME_TEXT_CHARS",
    "RUNTIME_PROTOCOL_VERSION",
    "RUNTIME_SCHEMA",
    "RuntimeAdapterError",
    "RuntimeCancelled",
    "RuntimeDenied",
    "RuntimeDispatcher",
    "RuntimeFailed",
    "RuntimeOperation",
    "RuntimeOutcome",
    "RuntimeOutcomeUnknown",
    "RuntimeProtocolError",
    "RuntimeRequest",
    "RuntimeResponse",
    "RuntimeResult",
    "RuntimeUnavailable",
    "UNKNOWN_IDEMPOTENCY_KEY",
    "UNKNOWN_REQUEST_ID",
    "decode_request",
    "decode_response",
    "encode_request",
    "encode_request_line",
    "encode_response",
    "encode_response_line",
    "negotiate_runtime_protocol",
    "read_message_line",
    "runtime_error_response",
    "serve",
]
