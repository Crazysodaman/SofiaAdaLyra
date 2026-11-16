"""Conformance for the independent SDK Validation Core scaffold.

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


def _run_lines(state_dir: Path, lines: list[str], *, timeout: int = 60):
    payload = "\n".join(lines) + "\n"
    return subprocess.run(
        [
            sys.executable, "-I", str(ENTRYPOINT),
            "--state-dir", str(state_dir),
        ],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
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


def test_check_imports_is_isolated_and_sdk_only():
    result = subprocess.run(
        [sys.executable, "-I", str(ENTRYPOINT), "--check-imports"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(ROOT),
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["sofia_core_loaded"] is False
    assert report["forbidden_prefixes_loaded"] == []
    loaded = report["loaded_sofia_modules"]
    assert "sofia.sdk" in loaded
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
    result, responses = _run_requests(tmp_path, [
        {"op": "hello", "protocol": "1.0"},
        {"op": "start"},
        {"op": "chat", "text": "alpha"},
        {"op": "chat", "text": "beta"},
        {"op": "history"},
        {"op": "health"},
        {"op": "stop"},
    ])
    assert result.returncode == 0, result.stderr
    assert len(responses) == 7
    assert all(item["status"] == "ok" for item in responses)

    hello, start, first, second, history, health, stop = responses
    assert hello["protocol"] == "1.0"
    assert hello["identity"]["uuid"] == TEST_UUID
    assert hello["scope"] == "core.private.sdk-validation"
    assert hello["engine"] == "DETERMINISTIC_TEST_ENGINE"
    assert hello["model_status"] == "MODEL_NOT_LOADED"
    assert hello["state"] == "idle"
    assert "sofia.core" not in hello["loaded_sofia_modules"]
    assert start["state"] == "ready"

    def expected(text: str, turn: int) -> str:
        digest = sha256(text.encode("utf-8")).hexdigest()[:16]
        return f"SDK-VC/1 turn={turn} sha256={digest} chars={len(text)}"

    assert first["reply"] == expected("alpha", 1)
    assert second["reply"] == expected("beta", 2)
    assert first["turn"] == 1 and second["turn"] == 2
    assert history["count"] == 2
    assert [item["user"] for item in history["turns"]] == ["alpha", "beta"]
    assert [item["core"] for item in history["turns"]] == [
        first["reply"], second["reply"],
    ]
    assert health["turn_count"] == 2
    assert health["started"] is True
    assert stop["state"] == "stopped"

    replay_dir = tmp_path / "replay"
    replay_result, replay = _run_requests(replay_dir, [
        {"op": "start"},
        {"op": "chat", "text": "alpha"},
        {"op": "chat", "text": "beta"},
        {"op": "stop"},
    ])
    assert replay_result.returncode == 0, replay_result.stderr
    assert [item["reply"] for item in replay[1:3]] == [
        first["reply"], second["reply"],
    ]


def test_history_is_durable_across_process_restart(tmp_path: Path):
    first_result, first = _run_requests(tmp_path, [
        {"op": "start"},
        {"op": "chat", "text": "first turn"},
        {"op": "stop"},
    ])
    assert first_result.returncode == 0, first_result.stderr
    assert all(item["status"] == "ok" for item in first)
    assert (tmp_path / "history.json").is_file()

    second_result, second = _run_requests(tmp_path, [
        {"op": "start"},
        {"op": "history"},
        {"op": "chat", "text": "second turn"},
        {"op": "stop"},
    ])
    assert second_result.returncode == 0, second_result.stderr
    assert second[0]["status"] == "ok"
    assert second[1]["count"] == 1
    assert second[1]["turns"][0]["user"] == "first turn"
    assert second[2]["turn"] == 2
    assert second[2]["reply"].startswith("SDK-VC/1 turn=2 ")

    third_result, third = _run_requests(tmp_path, [
        {"op": "start"},
        {"op": "history"},
        {"op": "stop"},
    ])
    assert third_result.returncode == 0, third_result.stderr
    assert third[1]["count"] == 2
    assert [item["user"] for item in third[1]["turns"]] == [
        "first turn", "second turn",
    ]


def test_bounded_input_rejection_is_explicit_and_nonfatal(tmp_path: Path):
    result, responses = _run_requests(tmp_path, [
        {"op": "chat", "text": "before start"},
        {"op": "start"},
        {"op": "chat", "text": "   "},
        {"op": "chat", "text": "x" * 4001},
        {"op": "unknown"},
        {"op": "chat", "text": "ok", "extra": True},
        {"op": "hello", "protocol": "2.0"},
        {"op": "chat", "text": "after errors"},
        {"op": "stop"},
    ])
    assert result.returncode == 0, result.stderr
    assert [item["status"] for item in responses] == [
        "error", "ok", "error", "error", "error", "error", "error", "ok", "ok",
    ]
    assert [item["error"] for item in responses if item["status"] == "error"] == [
        "not_started",
        "empty_text",
        "text_too_large",
        "unknown_op",
        "invalid_request",
        "incompatible_protocol",
    ]
    assert responses[7]["turn"] == 1
    assert responses[8]["state"] == "stopped"

    oversized = '{"op":"chat","text":"' + ("x" * 9000) + '"}'
    line_result = _run_lines(tmp_path, [
        oversized,
        '{"op":"start"}',
        "not json",
        '{"op":"stop"}',
    ])
    assert line_result.returncode == 0, line_result.stderr
    line_responses = [
        json.loads(line) for line in line_result.stdout.splitlines() if line.strip()
    ]
    assert [item["status"] for item in line_responses] == [
        "error", "ok", "error", "ok",
    ]
    assert line_responses[0]["error"] == "message_too_large"
    assert line_responses[2]["error"] == "invalid_json"
    assert line_responses[3]["state"] == "stopped"


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
