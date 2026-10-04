from datetime import datetime, timezone

import sofia.distributed.agent_tools as tools_module
from sofia.distributed.agent_tools import create_default_agent_dispatcher
from sofia.ops.model import HostTelemetry


def test_default_agent_advertises_read_only_ops_telemetry():
    dispatcher = create_default_agent_dispatcher(
        inference_models=("primary:model", "secondary:model"),
    )
    capabilities = {
        item.name: set(item.operations)
        for item in dispatcher.inventory()
    }

    assert "ops.telemetry" in capabilities
    assert capabilities["ops.telemetry"] == {"latest"}


def test_ops_telemetry_handler_returns_plain_normalized_snapshot(monkeypatch):
    monkeypatch.setattr(
        tools_module,
        "collect_local_telemetry",
        lambda: HostTelemetry(
            observed_at=datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc),
            cpu_percent=25.0,
            ram_used_bytes=4,
            ram_total_bytes=8,
            storage_free_bytes=16,
        ),
    )
    dispatcher = create_default_agent_dispatcher()

    result = dispatcher.execute("ops.telemetry", "latest", {})

    assert result["cpu_percent"] == 25.0
    assert result["ram_used_bytes"] == 4
    assert result["ram_total_bytes"] == 8
    assert result["storage_free_bytes"] == 16


class FakeOllama:
    def models(self):
        return {"models": [{"name": "primary:model"}]}

    def running(self):
        return {"models": [{"name": "secondary:model"}]}

    def show(self, name):
        return {"name": name}

    def pull(self, name):
        return {"status": "success", "model": name}

    def load(self, name, *, keep_alive="10m"):
        return {"loaded": name, "keep_alive": keep_alive}

    def unload(self, name):
        return {"unloaded": name}


def test_default_agent_advertises_ollama_inspect_and_manage(monkeypatch):
    monkeypatch.setattr(tools_module, "OllamaAdapter", FakeOllama)
    dispatcher = create_default_agent_dispatcher()
    capabilities = {
        item.name: set(item.operations)
        for item in dispatcher.inventory()
    }

    assert capabilities["llm.inspect"] == {
        "inference_policy",
        "models",
        "running",
        "show",
    }
    assert capabilities["llm.manage"] == {"pull", "load", "unload"}


def test_agent_ollama_lifecycle_uses_exact_requested_model(monkeypatch):
    monkeypatch.setattr(tools_module, "OllamaAdapter", FakeOllama)
    dispatcher = create_default_agent_dispatcher()

    assert dispatcher.execute(
        "llm.inspect", "show", {"model": "owner/model:any"}
    ) == {"name": "owner/model:any"}
    assert dispatcher.execute(
        "llm.manage", "pull", {"model": "owner/model:any"}
    )["model"] == "owner/model:any"
    assert dispatcher.execute(
        "llm.manage",
        "load",
        {"model": "owner/model:any", "keep_alive": "5m"},
    ) == {"loaded": "owner/model:any", "keep_alive": "5m"}
    assert dispatcher.execute(
        "llm.manage", "unload", {"model": "owner/model:any"}
    ) == {"unloaded": "owner/model:any"}


def test_agent_inference_policy_is_read_only_owner_configuration(monkeypatch):
    monkeypatch.setattr(tools_module, "OllamaAdapter", FakeOllama)
    dispatcher = create_default_agent_dispatcher(
        inference_models=("primary:model", "secondary:model"),
    )

    result = dispatcher.execute("llm.inspect", "inference_policy", {})

    assert result == {
        "allowed_models": ["primary:model", "secondary:model"]
    }


class FakePortainer:
    def __init__(self, base_url, api_key, endpoint_id):
        self.base_url = base_url
        self.api_key = api_key
        self.endpoint_id = endpoint_id

    def containers(self):
        return [{"Id": "container"}]

    def container(self, container):
        return {"Id": container}

    def container_stats(self, container):
        return {"container": container, "cpu_stats": {}}

    def info(self):
        return {"ServerVersion": "27.0"}

    def summary(self):
        return {"running": ("healthy",), "unhealthy": ()}

    def images(self):
        return [{"Id": "image"}]

    def volumes(self):
        return {"Volumes": []}

    def networks(self):
        return [{"Id": "network"}]

    def stacks(self):
        return [{"Id": 1, "Name": "stack"}]

    def restart(self, container, *, timeout_seconds=10):
        return {"container": container, "timeout_seconds": timeout_seconds}


def test_agent_portainer_advertises_expanded_read_only_docker_surface(
    monkeypatch,
):
    monkeypatch.setenv("SOFIA_AGENT_PORTAINER_URL", "http://portainer.local")
    monkeypatch.setenv("SOFIA_AGENT_PORTAINER_API_KEY", "secret")
    monkeypatch.setenv("SOFIA_AGENT_PORTAINER_ENDPOINT_ID", "2")
    monkeypatch.setattr(tools_module, "PortainerAdapter", FakePortainer)

    dispatcher = create_default_agent_dispatcher()
    capabilities = {
        item.name: set(item.operations)
        for item in dispatcher.inventory()
    }

    assert capabilities["container.inspect"] == {
        "list",
        "get",
        "stats",
        "info",
        "summary",
        "images",
        "volumes",
        "networks",
        "stacks",
    }
    assert capabilities["container.manage"] == {"restart"}
    assert dispatcher.execute(
        "container.inspect",
        "stats",
        {"container": "abc"},
    )["container"] == "abc"
    assert dispatcher.execute(
        "container.inspect",
        "summary",
        {},
    )["running"] == ["healthy"]
