from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sofia.config.model import ProviderConfiguration
from sofia.distributed.inference_client import ConfiguredRemoteInferenceClient
from sofia.safe.operator_stop import OperatorStopStore


def _client(tmp_path):
    return ConfiguredRemoteInferenceClient(
        tmp_path / "sofia.db",
        ca_file=tmp_path / "ca.pem",
        client_certificate=tmp_path / "client.pem",
        client_private_key=tmp_path / "client.key",
    )


def test_installed_model_preflight_does_not_mutate_remote(tmp_path, monkeypatch):
    client = _client(tmp_path)
    calls = []

    def operation(node_id, capability, operation, parameters):
        calls.append((capability, operation, parameters))
        return {"models": [{"name": "qwen3.5:9b"}]}

    monkeypatch.setattr(client, "_operation", operation)

    client.ensure_model_available(
        uuid4(),
        ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
        False,
    )

    assert calls == [("llm.inspect", "models", {})]


def test_missing_model_without_auto_provision_fails_closed(tmp_path, monkeypatch):
    client = _client(tmp_path)
    monkeypatch.setattr(
        client,
        "_operation",
        lambda *_: {"models": [{"name": "other:model"}]},
    )

    with pytest.raises(RuntimeError, match="not installed"):
        client.ensure_model_available(
            uuid4(),
            ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
            False,
        )


def test_missing_model_can_be_pulled_then_reverified(tmp_path, monkeypatch):
    client = _client(tmp_path)
    calls = []
    inventories = iter(
        (
            {"models": []},
            {"models": [{"name": "qwen3.5:9b"}]},
        )
    )

    def operation(node_id, capability, operation, parameters):
        calls.append((capability, operation, parameters))
        if (capability, operation) == ("llm.inspect", "models"):
            return next(inventories)
        if (capability, operation) == ("llm.manage", "pull"):
            return {"status": "success"}
        raise AssertionError((capability, operation))

    monkeypatch.setattr(client, "_operation", operation)

    client.ensure_model_available(
        uuid4(),
        ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
        True,
    )

    assert calls == [
        ("llm.inspect", "models", {}),
        ("llm.manage", "pull", {"model": "qwen3.5:9b"}),
        ("llm.inspect", "models", {}),
    ]


def test_pull_success_without_inventory_evidence_is_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path)
    inventories = iter(({"models": []}, {"models": []}))

    def operation(node_id, capability, operation, parameters):
        if (capability, operation) == ("llm.inspect", "models"):
            return next(inventories)
        return {"status": "success"}

    monkeypatch.setattr(client, "_operation", operation)

    with pytest.raises(RuntimeError, match="still absent"):
        client.ensure_model_available(
            uuid4(),
            ProviderConfiguration(provider="ollama", model="qwen3.5:9b"),
            True,
        )


def test_operator_stop_blocks_remote_model_management_before_transport(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path)
    OperatorStopStore(client.state_path).set(
        active=True,
        updated_by="Sparks",
        reason="test stop",
        at=datetime(2026, 9, 29, 22, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(PermissionError, match="operator stop"):
        client._operation(
            uuid4(),
            "llm.manage",
            "pull",
            {"model": "qwen3.5:9b"},
        )
