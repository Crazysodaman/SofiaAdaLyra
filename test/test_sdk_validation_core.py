"""Conformance for the independent SDK Validation Core facade integration.

These tests exercise a separate source tree and a real subprocess boundary.
They do not prove Worker supervision, signed installation, Core Link or real
inference; those remain PROBE items outside this scaffold.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "sdk_validation_core"
ENTRYPOINT = EXAMPLE / "entrypoint.py"
TEST_UUID = "4f2c9a17-6d3b-4e58-8a01-c7d9e2b6f430"
SOFIA_NAME = "Sofía Ada Lyra"
DEADLINE = "2099-01-01T00:00:00+00:00"
EXPIRED = "2000-01-01T00:00:00+00:00"


def _environment() -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(ROOT / "src"),
    }


def _command(*arguments: str) -> list[str]:
    return [sys.executable, "-P", "-s", str(ENTRYPOINT), *arguments]


def _request(
    operation: str,
    request_id: str,
    *,
    payload: dict[str, object] | None = None,
    deadline: str = DEADLINE,
    idempotency_key: str | None = None,
    protocol: str = "1.0",
) -> dict[str, object]:
    return {
        "protocol": protocol,
        "request_id": request_id,
        "idempotency_key": idempotency_key or f"idem-{request_id}",
        "operation": operation,
        "deadline": deadline,
        "payload": {} if payload is None else payload,
    }


def _run_lines(state_dir: Path, lines: list[str], *, timeout: int = 60):
    payload = "\n".join(lines) + "\n"
    return subprocess.run(
        _command("--state-dir", str(state_dir)),
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        env=_environment(),
        timeout=timeout,
    )


def _run_requests(state_dir: Path, requests: list[dict[str, object]]):
    result = _run_lines(
        state_dir,
        [json.dumps(item, ensure_ascii=False) for item in requests],
    )
    responses = [
        json.loads(line) for line in result.stdout.splitlines() if line.strip()
    ]
    return result, responses


def _assert_envelope(response: dict[str, object], request_id: str) -> None:
    assert response["protocol"] == "1.0"
    assert response["request_id"] == request_id
    assert response["idempotency_key"] == f"idem-{request_id}"
    assert response["code"] is None
    assert response["detail"] == ""
    assert response["outcome"] == "succeeded"


def test_check_imports_is_isolated_and_sdk_only():
    result = subprocess.run(
        _command("--check-imports"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        env=_environment(),
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["sofia_core_loaded"] is False
    assert report["forbidden_prefixes_loaded"] == []
    loaded = report["loaded_sofia_modules"]
    assert "sofia.sdk" in loaded
    assert "sofia.sdk.runtime" in loaded
    assert all(
        name == "sofia" or name == "sofia.sdk" or name.startswith("sofia.sdk.")
        for name in loaded
    )


def test_distinct_neutral_identity_and_definition():
    identity = json.loads((EXAMPLE / "identity.json").read_text("utf-8"))
    definition = json.loads((EXAMPLE / "definition.json").read_text("utf-8"))
    scope = json.loads((EXAMPLE / "scope.json").read_text("utf-8"))

    assert identity == {
        "schema": "aegis.identity.v1",
        "kind": "core",
        "uuid": TEST_UUID,
    }
    assert definition["identity"] == identity
    assert definition["name"] == "SDK Validation Core"
    assert definition["name"] not in {SOFIA_NAME, "Sofía"}
    assert definition["revision"] == 1
    assert scope["schema"] == "aegis.sdk-validation.scope.v1"
    assert scope["audience_kind"] == "private"
    assert scope["scope"] == "core.private.sdk-validation"
    assert scope["identity_id"] == TEST_UUID
    assert scope["definition_digest"] == scope["definition_digest"].lower()
    assert len(scope["definition_digest"]) == 64
    assert scope["contains_sofia_assets"] is False
    assert scope["contains_owner_secrets"] is False

    from sofia.sdk.core_definition import CoreDefinition

    parsed = CoreDefinition.from_payload(definition)
    assert parsed.identity.canonical_uuid == TEST_UUID
    assert parsed.digest == scope["definition_digest"]
    assert parsed.revision == scope["definition_revision"]
    assert parsed.runtime_release_sha256 == scope["runtime_release_sha256"]


def test_hello_and_deterministic_multi_turn_with_clean_stop(tmp_path: Path):
    requests = [
        _request("hello", "req-1"),
        _request("start", "req-2"),
        _request("chat", "req-3", payload={"text": "alpha"}),
        _request("chat", "req-4", payload={"text": "beta"}),
        _request("history", "req-5"),
        _request("health", "req-6"),
        _request("stop", "req-7"),
    ]
    result, responses = _run_requests(tmp_path, requests)
    assert result.returncode == 0, result.stderr
    assert len(responses) == 7
    assert all(item["outcome"] == "succeeded" for item in responses)
    for response, request in zip(responses, requests):
        _assert_envelope(response, request["request_id"])

    hello, start, first, second, history, health, stop = responses
    hello_payload = hello["payload"]
    assert hello_payload["protocol"] == "1.0"
    assert hello_payload["identity"]["uuid"] == TEST_UUID
    assert hello_payload["scope"] == "core.private.sdk-validation"
    assert hello_payload["engine"] == "DETERMINISTIC_TEST_ENGINE"
    assert hello_payload["model_status"] == "MODEL_NOT_LOADED"
    assert hello_payload["state"] == "idle"
    assert "sofia.core" not in hello_payload["loaded_sofia_modules"]
    assert start["payload"]["state"] == "ready"

    def expected(text: str, turn: int) -> str:
        digest = sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"SDK-VC/1 turn={turn} sha256={digest} chars={len(text)}"

    first_payload = first["payload"]
    second_payload = second["payload"]
    assert first_payload["reply"] == expected("alpha", 1)
    assert second_payload["reply"] == expected("beta", 2)
    assert first_payload["turn"] == 1 and second_payload["turn"] == 2
    assert history["payload"]["count"] == 2
    assert [item["user"] for item in history["payload"]["turns"]] == [
        "alpha", "beta",
    ]
    assert [item["core"] for item in history["payload"]["turns"]] == [
        first_payload["reply"], second_payload["reply"],
    ]
    assert health["payload"]["turn_count"] == 2
    assert health["payload"]["started"] is True
    assert stop["payload"]["state"] == "stopped"

    replay_dir = tmp_path / "replay"
    replay_requests = [
        _request("start", "replay-start"),
        _request("chat", "replay-chat-1", payload={"text": "alpha"}),
        _request("chat", "replay-chat-2", payload={"text": "beta"}),
        _request("stop", "replay-stop"),
    ]
    replay_result, replay = _run_requests(replay_dir, replay_requests)
    assert replay_result.returncode == 0, replay_result.stderr
    assert [item["payload"]["reply"] for item in replay[1:3]] == [
        first_payload["reply"], second_payload["reply"],
    ]


def test_history_is_durable_across_process_restart(tmp_path: Path):
    first_result, first = _run_requests(tmp_path, [
        _request("start", "first-start"),
        _request("chat", "first-chat", payload={"text": "first turn"}),
        _request("stop", "first-stop"),
    ])
    assert first_result.returncode == 0, first_result.stderr
    assert all(item["outcome"] == "succeeded" for item in first)
    assert (tmp_path / "history.json").is_file()

    second_result, second = _run_requests(tmp_path, [
        _request("start", "second-start"),
        _request("history", "second-history"),
        _request("chat", "second-chat", payload={"text": "second turn"}),
        _request("stop", "second-stop"),
    ])
    assert second_result.returncode == 0, second_result.stderr
    assert second[0]["outcome"] == "succeeded"
    assert second[1]["payload"]["count"] == 1
    assert second[1]["payload"]["turns"][0]["user"] == "first turn"
    assert second[2]["payload"]["turn"] == 2
    assert second[2]["payload"]["reply"].startswith("SDK-VC/1 turn=2 ")

    third_result, third = _run_requests(tmp_path, [
        _request("start", "third-start"),
        _request("history", "third-history"),
        _request("stop", "third-stop"),
    ])
    assert third_result.returncode == 0, third_result.stderr
    assert third[1]["payload"]["count"] == 2
    assert [item["user"] for item in third[1]["payload"]["turns"]] == [
        "first turn", "second turn",
    ]


def test_duplicate_request_is_idempotent_across_process(tmp_path: Path):
    request = _request("chat", "duplicate-chat", payload={"text": "once"})
    result, responses = _run_requests(tmp_path, [
        _request("start", "dup-start"),
        request,
        request,
        _request("history", "dup-history"),
        _request("stop", "dup-stop"),
    ])
    assert result.returncode == 0, result.stderr
    assert all(item["outcome"] == "succeeded" for item in responses)
    assert responses[1]["payload"]["reply"] == responses[2]["payload"]["reply"]
    assert responses[3]["payload"]["count"] == 1


def test_bounded_input_rejection_is_explicit_and_nonfatal(tmp_path: Path):
    extra = _request("chat", "extra-field", payload={"text": "ok"})
    extra["extra"] = True
    result, responses = _run_requests(tmp_path, [
        _request("chat", "before-start", payload={"text": "before start"}),
        _request("start", "start"),
        _request("chat", "empty", payload={"text": "   "}),
        _request("chat", "too-large", payload={"text": "x" * 4001}),
        _request("unknown", "unknown-op"),
        extra,
        _request("hello", "bad-version", protocol="2.0"),
        _request("chat", "after-errors", payload={"text": "after errors"}),
        _request("stop", "stop"),
    ])
    assert result.returncode == 0, result.stderr
    assert [item["outcome"] for item in responses] == [
        "denied", "succeeded", "denied", "denied", "denied", "denied",
        "denied", "succeeded", "succeeded",
    ]
    assert [item["code"] for item in responses if item["outcome"] != "succeeded"] == [
        "not_started",
        "empty_text",
        "text_too_large",
        "unknown_op",
        "unknown_field",
        "unsupported_protocol",
    ]
    assert responses[7]["payload"]["turn"] == 1
    assert responses[8]["payload"]["state"] == "stopped"

    oversized = '{"op":"chat","text":"' + ("x" * 9000) + '"}'
    line_result = _run_lines(tmp_path, [
        oversized,
        json.dumps(_request("start", "line-start")),
        "not json",
        json.dumps(_request("stop", "line-stop")),
    ])
    assert line_result.returncode == 0, line_result.stderr
    line_responses = [
        json.loads(line) for line in line_result.stdout.splitlines() if line.strip()
    ]
    assert [item["outcome"] for item in line_responses] == [
        "denied", "succeeded", "failed", "succeeded",
    ]
    assert line_responses[0]["code"] == "message_too_large"
    assert line_responses[2]["code"] == "invalid_json"
    assert line_responses[3]["payload"]["state"] == "stopped"


def test_example_source_imports_only_public_sdk():
    files = sorted(EXAMPLE.rglob("*.py"))
    assert files
    forbidden = re.compile(
        r"(?m)^\s*(?:from|import)\s+"
        r"sofia\.(?:core|application|platform)(?:\.[A-Za-z0-9_]+)*"
    )
    sofia_import = re.compile(
        r"(?m)^\s*(?:from|import)\s+(sofia(?:\.[A-Za-z0-9_]+)*)"
    )
    for path in files:
        source = path.read_text("utf-8")
        assert forbidden.search(source) is None, path
        for name in sofia_import.findall(source):
            assert (
                name == "sofia"
                or name == "sofia.sdk"
                or name.startswith("sofia.sdk.")
            ), (path, name)
