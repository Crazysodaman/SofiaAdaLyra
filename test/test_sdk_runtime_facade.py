"""Conformance for the portable ``sofia.sdk.runtime`` facade."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from sofia.sdk.runtime import (
    CoreRuntimeAdapter,
    MAX_RUNTIME_MESSAGE_BYTES,
    RUNTIME_PROTOCOL_VERSION,
    RuntimeCancelled,
    RuntimeDenied,
    RuntimeDispatcher,
    RuntimeOperation,
    RuntimeOutcome,
    RuntimeOutcomeUnknown,
    RuntimeProtocolError,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeResult,
    RuntimeUnavailable,
    UNKNOWN_IDEMPOTENCY_KEY,
    UNKNOWN_REQUEST_ID,
    decode_request,
    decode_response,
    encode_request,
    encode_request_line,
    encode_response,
    encode_response_line,
    negotiate_runtime_protocol,
)
from sofia.sdk.contracts import ProtocolVersion


ROOT = Path(__file__).resolve().parents[1]
FACADE = ROOT / "src" / "sofia" / "sdk" / "runtime.py"
EXAMPLE = ROOT / "examples" / "sdk_validation_core"
NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=timezone.utc)
DEADLINE = NOW + timedelta(minutes=5)


def _request(
    operation: RuntimeOperation = RuntimeOperation.CHAT,
    *,
    request_id: str = "req-1",
    idempotency_key: str = "idem-1",
    payload: dict[str, object] | None = None,
    deadline: datetime = DEADLINE,
) -> RuntimeRequest:
    return RuntimeRequest(
        protocol=RUNTIME_PROTOCOL_VERSION,
        request_id=request_id,
        idempotency_key=idempotency_key,
        operation=operation,
        deadline=deadline,
        payload={"text": "hello"} if payload is None else payload,
    )


class RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def hello(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("hello")
        return RuntimeResult.succeeded({"protocol": str(request.protocol)})

    def start(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("start")
        return RuntimeResult.succeeded({"state": "ready"})

    def chat(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("chat")
        return RuntimeResult.succeeded({"reply": request.payload["text"]})

    def task(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("task")
        return RuntimeResult.succeeded({"task": request.payload["task"]})

    def history(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("history")
        return RuntimeResult.succeeded({"turns": []})

    def health(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("health")
        return RuntimeResult.succeeded({"state": "ready"})

    def stop(self, request: RuntimeRequest) -> RuntimeResult:
        self.calls.append("stop")
        return RuntimeResult.succeeded({"state": "stopped"})


def _response(
    *,
    outcome: RuntimeOutcome = RuntimeOutcome.SUCCEEDED,
    code: str | None = None,
    detail: str = "",
    payload: dict[str, object] | None = None,
) -> RuntimeResponse:
    return RuntimeResponse(
        protocol=RUNTIME_PROTOCOL_VERSION,
        request_id="req-1",
        idempotency_key="idem-1",
        outcome=outcome,
        code=code,
        detail=detail,
        payload={} if payload is None else payload,
        completed_at=NOW,
    )


def test_facade_adapter_is_structural() -> None:
    assert isinstance(RecordingAdapter(), CoreRuntimeAdapter)


def test_request_and_response_round_trip() -> None:
    request = _request(payload={"text": "hello"})
    raw = encode_request(request)
    assert decode_request(raw) == request
    line = encode_request_line(request)
    assert line.endswith(b"\n")
    assert b"\n" not in line[:-1]

    response = _response(payload={"reply": "hello"})
    raw_response = encode_response(response)
    assert decode_response(raw_response) == response
    response_line = encode_response_line(response)
    assert response_line.endswith(b"\n")
    assert b"\n" not in response_line[:-1]


def test_unknown_protocol_version_is_rejected() -> None:
    assert negotiate_runtime_protocol("1.0") == ProtocolVersion(1, 0)
    assert negotiate_runtime_protocol(ProtocolVersion(1, 0)) == ProtocolVersion(1, 0)
    for version in ("1.1", "2.0"):
        with pytest.raises(RuntimeProtocolError) as caught:
            negotiate_runtime_protocol(version)
        assert caught.value.code == "unsupported_protocol"

        document = _request().to_payload()
        document["protocol"] = version
        with pytest.raises(RuntimeProtocolError) as caught:
            decode_request(json.dumps(document).encode("utf-8"))
        assert caught.value.code == "unsupported_protocol"

    for value in ("0.0", None, "1", "1.0.0", (1,), (1, 0, 2)):
        with pytest.raises(RuntimeProtocolError) as caught:
            negotiate_runtime_protocol(value)
        assert caught.value.code == "malformed_protocol"


def test_unknown_and_missing_fields_are_rejected() -> None:
    document = _request().to_payload()
    document["unexpected"] = True
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_request(json.dumps(document).encode("utf-8"))
    assert caught.value.code == "unknown_field"

    document = _request().to_payload()
    del document["deadline"]
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_request(json.dumps(document).encode("utf-8"))
    assert caught.value.code == "missing_field"

    document = _response().to_payload()
    document["unexpected"] = True
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_response(json.dumps(document).encode("utf-8"))
    assert caught.value.code == "unknown_field"

    document = _request(payload={"text": "ok"}).to_payload()
    document["payload"] = {"text": "ok", "extra": True}
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_request(json.dumps(document).encode("utf-8"))
    assert caught.value.code == "unknown_field"

    document = _request(RuntimeOperation.START, payload={}).to_payload()
    document["payload"] = {"unexpected": True}
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_request(json.dumps(document).encode("utf-8"))
    assert caught.value.code == "unknown_field"


def test_bounded_payload_is_enforced() -> None:
    with pytest.raises(RuntimeProtocolError) as caught:
        _request(payload={"text": "x" * 4001})
    assert caught.value.code == "text_too_large"

    with pytest.raises(RuntimeProtocolError) as caught:
        _request(
            RuntimeOperation.TASK,
            payload={"task": "echo", "arguments": {"blob": "x" * 50000}},
        )
    assert caught.value.code == "payload_too_large"

    oversized = b'{"blob":"' + b"x" * (MAX_RUNTIME_MESSAGE_BYTES + 1) + b'"}'
    with pytest.raises(RuntimeProtocolError) as caught:
        decode_request(oversized)
    assert caught.value.code == "message_too_large"

    with pytest.raises(RuntimeProtocolError) as caught:
        _request(
            RuntimeOperation.TASK,
            payload={"task": "echo", "arguments": [1, 2, 3]},
        )
    assert caught.value.code == "invalid_arguments"


def test_duplicate_request_idempotency() -> None:
    adapter = RecordingAdapter()
    dispatcher = RuntimeDispatcher(adapter)
    request = _request(payload={"text": "once"})
    first = dispatcher.dispatch(request, now=NOW)
    second = dispatcher.dispatch(request, now=NOW)
    assert first.outcome is RuntimeOutcome.SUCCEEDED
    assert second == first
    assert adapter.calls.count("chat") == 1

    retry = _request(
        payload={"text": "once"}, request_id="req-2", idempotency_key="idem-1"
    )
    replay = dispatcher.dispatch(retry, now=NOW)
    assert replay.outcome is RuntimeOutcome.SUCCEEDED
    assert replay.request_id == "req-2"
    assert replay.payload == first.payload
    assert adapter.calls.count("chat") == 1

    conflict = _request(
        payload={"text": "different"}, request_id="req-1", idempotency_key="idem-1"
    )
    conflicted = dispatcher.dispatch(conflict, now=NOW)
    assert conflicted.outcome is RuntimeOutcome.DENIED
    assert conflicted.code == "idempotency_conflict"

    duplicate_id = _request(
        payload={"text": "once"}, request_id="req-1", idempotency_key="idem-2"
    )
    duplicate = dispatcher.dispatch(duplicate_id, now=NOW)
    assert duplicate.outcome is RuntimeOutcome.DENIED
    assert duplicate.code == "duplicate_request_id"
    assert adapter.calls.count("chat") == 1


def test_deadline_cancellation_unavailable_and_unknown() -> None:
    adapter = RecordingAdapter()
    dispatcher = RuntimeDispatcher(adapter)
    expired = _request(deadline=NOW - timedelta(seconds=1))
    response = dispatcher.dispatch(expired, now=NOW)
    assert response.outcome is RuntimeOutcome.FAILED
    assert response.code == "deadline_exceeded"
    assert adapter.calls == []

    class DeniedAdapter(RecordingAdapter):
        def chat(self, request: RuntimeRequest) -> RuntimeResult:
            raise RuntimeDenied("not_started", "start first")

    denied = RuntimeDispatcher(DeniedAdapter()).dispatch(
        _request(), now=NOW
    )
    assert denied.outcome is RuntimeOutcome.DENIED
    assert denied.code == "not_started"

    class CancelledAdapter(RecordingAdapter):
        def chat(self, request: RuntimeRequest) -> RuntimeResult:
            raise RuntimeCancelled()

    cancelled = RuntimeDispatcher(CancelledAdapter()).dispatch(
        _request(), now=NOW
    )
    assert cancelled.outcome is RuntimeOutcome.FAILED
    assert cancelled.code == "cancelled"

    class UnavailableAdapter(RecordingAdapter):
        def chat(self, request: RuntimeRequest) -> RuntimeResult:
            raise RuntimeUnavailable("engine_unavailable", "no engine")

    unavailable = RuntimeDispatcher(UnavailableAdapter()).dispatch(
        _request(), now=NOW
    )
    assert unavailable.outcome is RuntimeOutcome.UNAVAILABLE
    assert unavailable.code == "engine_unavailable"

    class UnknownAdapter(RecordingAdapter):
        def chat(self, request: RuntimeRequest) -> RuntimeResult:
            raise RuntimeOutcomeUnknown("effect_unknown", "lost confirmation")

    unknown = RuntimeDispatcher(UnknownAdapter()).dispatch(
        _request(), now=NOW
    )
    assert unknown.outcome is RuntimeOutcome.OUTCOME_UNKNOWN
    assert unknown.code == "effect_unknown"

    class BrokenAdapter(RecordingAdapter):
        def chat(self, request: RuntimeRequest) -> RuntimeResult:
            raise RuntimeError("boom")

    broken = RuntimeDispatcher(BrokenAdapter()).dispatch(
        _request(), now=NOW
    )
    assert broken.outcome is RuntimeOutcome.OUTCOME_UNKNOWN
    assert broken.code == "internal_error"


def test_handle_line_preserves_typed_rejections() -> None:
    dispatcher = RuntimeDispatcher(RecordingAdapter())
    invalid_json = decode_response(dispatcher.handle_line(b"not json", now=NOW))
    assert invalid_json.outcome is RuntimeOutcome.FAILED
    assert invalid_json.code == "invalid_json"
    assert invalid_json.request_id == UNKNOWN_REQUEST_ID
    assert invalid_json.idempotency_key == UNKNOWN_IDEMPOTENCY_KEY

    document = _request().to_payload()
    document["unexpected"] = True
    unknown_field = decode_response(
        dispatcher.handle_line(json.dumps(document).encode("utf-8"), now=NOW)
    )
    assert unknown_field.outcome is RuntimeOutcome.DENIED
    assert unknown_field.code == "unknown_field"

    start = decode_response(
        dispatcher.handle_line(
            encode_request(_request(RuntimeOperation.START, payload={})),
            now=NOW,
        )
    )
    assert start.outcome is RuntimeOutcome.SUCCEEDED
    assert start.payload == {"state": "ready"}


def test_subprocess_import_isolation_keeps_sofia_core_absent() -> None:
    code = (
        "import sys; import sofia.sdk.runtime as r; "
        "assert r.RUNTIME_PROTOCOL_VERSION.major == 1; "
        "assert not any(name == 'sofia.core' or name.startswith('sofia.core.') "
        "for name in sys.modules), sorted(sys.modules); "
        "assert not any(name == 'sofia.application' "
        "or name.startswith('sofia.application.') for name in sys.modules); "
        "assert not any(name == 'sofia.platform' "
        "or name.startswith('sofia.platform.') for name in sys.modules)"
    )
    completed = subprocess.run(
        [sys.executable, "-P", "-s", "-c", code],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add("." * node.level + (node.module or ""))
    return imports


def test_facade_and_example_have_no_private_escapes() -> None:
    facade_imports = _imports(FACADE)
    assert not any(
        name == "sofia.core"
        or name.startswith("sofia.core.")
        or name == "sofia.application"
        or name.startswith("sofia.application.")
        or name == "sofia.platform"
        or name.startswith("sofia.platform.")
        for name in facade_imports
    )
    assert not any(name.startswith("sofia.") for name in facade_imports)

    for path in sorted(EXAMPLE.rglob("*.py")):
        imports = _imports(path)
        assert not any(
            name == "sofia.core"
            or name.startswith("sofia.core.")
            or name == "sofia.application"
            or name.startswith("sofia.application.")
            or name == "sofia.platform"
            or name.startswith("sofia.platform.")
            for name in imports
        ), path
        for name in imports:
            if name == "sofia" or name.startswith("sofia."):
                assert name == "sofia" or name == "sofia.sdk" or name.startswith(
                    "sofia.sdk."
                ), (path, name)
