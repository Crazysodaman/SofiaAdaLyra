"""Verify real default state reaches Ollama without invoking a live model."""

from dataclasses import replace
from types import SimpleNamespace

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.composition.root import compose
from sofia.config import create_default_configuration
from sofia.environment.config import EnvironmentConfiguration


class CapturingOllamaClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def chat(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(
                content="Captured.",
                tool_calls=(),
            ),
        )


def test_default_runtime_sends_canonical_state_with_context_budget(tmp_path):
    default = create_default_configuration()
    configuration = replace(
        default,
        state_path=tmp_path / "sofia.db",
        filesystem_root=tmp_path,
        environment=EnvironmentConfiguration(),
    )
    runtime = compose(configuration)
    provider = runtime.cognitive_system.engine.provider
    assert isinstance(provider, OllamaProvider)

    client = CapturingOllamaClient()
    provider.client = client
    started = False

    try:
        runtime.start()
        started = True
        response = runtime.respond(
            CognitiveRequest(
                messages=(
                    CognitiveMessage(
                        role=CognitiveRole.USER,
                        content=(
                            "Who are you, and what are your canonical "
                            "measurements and clothing?"
                        ),
                    ),
                ),
            )
        )

        assert response.content == "Captured."
        assert len(client.requests) == 1
        sent = client.requests[0]
        assert sent["model"] == default.provider.model
        assert sent["options"]["num_ctx"] == 20000
        assert sent["think"] is False
        assert sent["messages"][0]["role"] == "system"
        system = sent["messages"][0]["content"]

        identity = runtime.identity
        embodiment = runtime.embodiment
        operational = runtime.operational_state
        assert identity is not None
        assert embodiment is not None
        assert operational is not None
        assert identity.instance_id != operational.runtime_id
        assert f"Name: {identity.name}" in system
        assert f"Instance ID: {identity.instance_id}" in system
        assert f"Runtime ID: {operational.runtime_id}" in system

        physical = embodiment.physical_self
        assert "Representation status: representational embodiment" in system
        assert physical.measurements
        for name, measurement in physical.measurements:
            assert f"- {name}: {measurement.value} {measurement.unit}" in system

        assert embodiment.clothing.items
        for item in embodiment.clothing.items:
            assert f"- {item.category}: {item.specification}" in system

        # Missing source facts must stay UNKNOWN; the provider must receive
        # that boundary rather than infer nonexistence from missing evidence.
        assert "If a category is marked UNKNOWN, do not invent a value." in system
        assert "If an authoritative source says UNKNOWN" in system
    finally:
        if started:
            runtime.shutdown()
