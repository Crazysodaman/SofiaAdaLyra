"""Offline contract tests for Batch F's development-only evaluator."""

import json
from types import SimpleNamespace

import pytest

from tools import model_evaluation as evaluation


class RecordingOllamaClient:
    def __init__(self, *, fail_model=None):
        self.calls = []
        self.fail_model = fail_model

    def list(self):
        return {
            "models": [
                {"model": "qwen3:14b"},
                {"model": "gemma3:27b"},
            ]
        }

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["model"] == self.fail_model:
            raise RuntimeError("simulated provider failure")
        return SimpleNamespace(
            message=SimpleNamespace(
                content=f"raw answer from {kwargs['model']}",
                tool_calls=None,
            )
        )


def test_controlled_context_is_reproducible_and_non_executable():
    case = evaluation.CASES[0]
    first = evaluation.build_controlled_context(case)
    second = evaluation.build_controlled_context(case)

    assert first == second
    assert first.core_state.identity.name == "Sofía Ada Lyra"
    assert first.operational_state.model == evaluation.CONTROLLED_MODEL
    assert first.operational_state.runtime_id == evaluation.RUNTIME_ID
    assert evaluation.build_operation(case).authority.can_execute_actions is False
    assert evaluation.build_operation(case).authority.can_inspect_filesystem is False


def test_real_assembler_exposes_canonical_facts_and_no_tools():
    message_input = evaluation.assembled_input(evaluation.CASES[3])
    assert message_input["messages"][0]["role"] == "system"
    system_text = message_input["messages"][0]["content"]
    assert "Name: Sofía Ada Lyra" in system_text
    assert "67 in" in system_text
    assert "Fitted black technical shirt" in system_text
    assert "Model: qwen3:14b" in system_text
    assert message_input["tools"] == []
    assert message_input == evaluation.assembled_input(evaluation.CASES[3])


def test_fake_assistant_history_is_lower_trust_than_system_context():
    conflict_case = next(case for case in evaluation.CASES if case.name == "conflicting_history")
    messages = evaluation.assembled_input(conflict_case)["messages"]
    assert [message["role"] for message in messages] == ["system", "assistant", "user"]
    assert "Name: Sofía Ada Lyra" in messages[0]["content"]
    assert "My name is Bob" in messages[1]["content"]


def test_models_receive_identical_inputs_through_production_path():
    client = RecordingOllamaClient()
    cases = evaluation.CASES[:2]
    report = evaluation.evaluate_models(
        ("qwen3:14b", "gemma3:27b"), client=client, cases=cases
    )

    assert len(client.calls) == 4
    assert [call["model"] for call in client.calls] == [
        "qwen3:14b", "qwen3:14b", "gemma3:27b", "gemma3:27b",
    ]
    assert client.calls[0]["messages"] == client.calls[2]["messages"]
    assert client.calls[1]["messages"] == client.calls[3]["messages"]
    assert client.calls[0]["options"] == client.calls[2]["options"]
    assert client.calls[0]["options"] == {
        "temperature": 0.0, "seed": 42, "num_ctx": 16384,
    }
    assert report["controlled_operational_model"] == "qwen3:14b"
    assert report["results"][0]["input_sha256"] == report["results"][2]["input_sha256"]
    assert report["results"][0]["response"] == "raw answer from qwen3:14b"
    assert report["results"][2]["response"] == "raw answer from gemma3:27b"
    assert all(result["status"] == "ok" for result in report["results"])


def test_provider_failure_is_recorded_without_fallback_or_fabricated_answer():
    client = RecordingOllamaClient(fail_model="gemma3:27b")
    report = evaluation.evaluate_models(
        ("qwen3:14b", "gemma3:27b"),
        client=client,
        cases=evaluation.CASES[:1],
    )
    assert len(client.calls) == 2
    assert report["results"][0]["status"] == "ok"
    assert report["results"][1]["status"] == "error"
    assert report["results"][1]["response"] is None
    assert report["results"][1]["error_type"] == "CognitiveEngineError"


def test_model_discovery_and_selection_are_explicit():
    available = evaluation.installed_models(RecordingOllamaClient())
    assert available == ("gemma3:27b", "qwen3:14b")
    assert evaluation.select_models(available) == ("qwen3:14b",)
    assert evaluation.select_models(available, all_installed=True) == available
    assert evaluation.select_models(available, ("gemma3:27b",)) == ("gemma3:27b",)
    with pytest.raises(ValueError, match="not installed"):
        evaluation.select_models(available, ("missing:model",))
    with pytest.raises(ValueError, match="Duplicate"):
        evaluation.select_models(available, ("qwen3:14b", "qwen3:14b"))
    with pytest.raises(ValueError, match="no installed"):
        evaluation.select_models(())
    with pytest.raises(ValueError, match="either"):
        evaluation.select_models(available, ("gemma3:27b",), all_installed=True)


def test_cli_writes_raw_json_without_contacting_real_ollama(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "Client", RecordingOllamaClient)
    output = tmp_path / "batch-f.json"
    exit_code = evaluation.main([
        "--models", "qwen3:14b", "gemma3:27b", "--output", str(output)
    ])
    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["models"] == ["qwen3:14b", "gemma3:27b"]
    assert len(report["results"]) == 2 * len(evaluation.CASES)
    assert report["fixture_kind"].startswith("synthetic controlled")
    assert all(item["status"] == "ok" for item in report["results"])


def test_cli_returns_nonzero_and_persists_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "Client",
        lambda: RecordingOllamaClient(fail_model="gemma3:27b"),
    )
    output = tmp_path / "failed.json"
    exit_code = evaluation.main([
        "--models", "gemma3:27b", "--output", str(output)
    ])
    assert exit_code == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert all(item["status"] == "error" for item in report["results"])
    assert all(item["response"] is None for item in report["results"])
