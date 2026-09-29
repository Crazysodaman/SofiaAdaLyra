from pathlib import Path

import pytest

from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.fleet_engine import FleetPlacedCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)
from sofia.cognition.routing import (
    CognitiveEngineRegistry,
    CognitiveRoute,
    CognitiveRoutingPolicy,
    RoutingCognitiveEngine,
)
from sofia.composition.root import _create_cognitive_engine
from sofia.config import create_default_configuration
from sofia.ops.capability import OpsToolService
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.config.model import (
    CognitiveRoutingConfiguration,
    FleetCognitionConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)


class QueueEngine(CognitiveEngine):
    def __init__(self, *results):
        self.results = list(results)
        self.requests = []

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        self.requests.append(request)
        if not self.results:
            raise AssertionError("QueueEngine received an unexpected request")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def request(text: str, *, tools=()) -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="Canonical Sofía context.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=text,
            ),
        ),
        tools=tools,
    )


def registry(primary: CognitiveEngine, secondary: CognitiveEngine):
    return CognitiveEngineRegistry(
        primary=primary,
        secondary=secondary,
    )


def test_short_social_request_routes_to_secondary():
    primary = QueueEngine()
    secondary = QueueEngine(CognitiveResponse(content="fast"))
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(request("hru"))

    assert response.content == "fast"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.FAST
    assert len(primary.requests) == 0
    assert len(secondary.requests) == 1


def test_technical_request_routes_to_primary():
    primary = QueueEngine(CognitiveResponse(content="technical"))
    secondary = QueueEngine()
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(
        request(
            "Debug this Python traceback from my Docker service and explain "
            "the architecture problem."
        )
    )

    assert response.content == "technical"
    assert engine.last_decision is not None
    assert engine.last_decision.route in {
        CognitiveRoute.STANDARD,
        CognitiveRoute.DEEP,
    }
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_tool_request_routes_to_primary():
    tool = CognitiveToolDefinition(
        name="system.inspect",
        description="Inspect the current system.",
        parameters={"type": "object"},
    )
    primary = QueueEngine(CognitiveResponse(content="inspect"))
    secondary = QueueEngine()
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    engine.respond(request("Check the system state.", tools=(tool,)))

    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.DEEP
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_explicit_open_model_request_routes_to_secondary():
    primary = QueueEngine()
    secondary = QueueEngine(CognitiveResponse(content="open"))
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(
        request("Use the open model for this casual conversation.")
    )

    assert response.content == "open"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.OPEN


def test_secondary_failure_falls_back_to_primary():
    secondary = QueueEngine(
        CognitiveEngineError("secondary failed")
    )
    primary = QueueEngine(CognitiveResponse(content="primary fallback"))
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(request("hello"))

    assert response.content == "primary fallback"
    assert len(secondary.requests) == 1
    assert len(primary.requests) == 1


def test_primary_failure_falls_back_to_secondary():
    primary = QueueEngine(
        CognitiveEngineError("primary failed")
    )
    secondary = QueueEngine(CognitiveResponse(content="secondary fallback"))
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(
        request(
            "Debug this Python Docker traceback and explain the architecture."
        )
    )

    assert response.content == "secondary fallback"
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 1


def test_verify_uses_primary_secondary_primary_sequence():
    primary = QueueEngine(
        CognitiveResponse(content="draft"),
        CognitiveResponse(content="final"),
    )
    secondary = QueueEngine(
        CognitiveResponse(content="critique")
    )
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    response = engine.respond(
        request("Please verify this answer before replying.")
    )

    assert response.content == "final"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.VERIFY
    assert len(primary.requests) == 2
    assert len(secondary.requests) == 1
    critique_request = secondary.requests[0]
    assert critique_request.tools == ()
    assert critique_request.allow_tools is False
    synthesis_request = primary.requests[1]
    assert synthesis_request.tools == ()
    assert synthesis_request.allow_tools is False
    assert "Reviewer critique:" in synthesis_request.messages[-1].content
    assert "critique" in synthesis_request.messages[-1].content


def test_verify_never_duplicates_tool_call():
    tool = CognitiveToolDefinition(
        name="service.restart",
        description="Restart a service.",
        parameters={"type": "object"},
    )
    response = CognitiveResponse(
        content="",
        tool_calls=(
            CognitiveToolCall(
                name="service.restart",
                arguments={"name": "example"},
                call_id="call-1",
            ),
        ),
    )
    primary = QueueEngine(response)
    secondary = QueueEngine()
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    result = engine.respond(
        request("Restart the service and verify it.", tools=(tool,))
    )

    assert result is response
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.VERIFY
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_verify_reviews_completed_tool_text_without_secondary_tools():
    tool = CognitiveToolDefinition(
        name="service.restart",
        description="Restart a service.",
        parameters={"type": "object"},
    )
    primary = QueueEngine(
        CognitiveResponse(content="draft after tool work"),
        CognitiveResponse(content="verified final"),
    )
    secondary = QueueEngine(
        CognitiveResponse(content="review critique")
    )
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    result = engine.respond(
        request("Restart the service and verify it.", tools=(tool,))
    )

    assert result.content == "verified final"
    assert len(primary.requests) == 2
    assert len(secondary.requests) == 1
    assert secondary.requests[0].tools == ()
    assert secondary.requests[0].allow_tools is False
    assert primary.requests[1].tools == ()
    assert primary.requests[1].allow_tools is False


def test_verify_can_be_disabled_without_changing_policy():
    primary = QueueEngine(CognitiveResponse(content="single pass"))
    secondary = QueueEngine()
    engine = RoutingCognitiveEngine(
        registry(primary, secondary),
        verify_enabled=False,
    )

    response = engine.respond(
        request("Please verify this answer.")
    )

    assert response.content == "single pass"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.VERIFY
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_routing_policy_is_deterministic():
    policy = CognitiveRoutingPolicy()
    value = request("hello")

    first = policy.decide(value)
    second = policy.decide(value)

    assert first == second


def test_enabled_routing_configuration_requires_both_models():
    with pytest.raises(ValueError, match="primary and secondary"):
        CognitiveRoutingConfiguration(
            enabled=True,
            primary=ProviderConfiguration(
                provider="test-llm",
                model="primary",
            ),
        )


def test_default_configuration_can_enable_selected_models(monkeypatch):
    monkeypatch.setenv("SOFIA_COGNITION_ROUTING_ENABLED", "1")
    monkeypatch.setenv(
        "SOFIA_COGNITION_PRIMARY_MODEL",
        "qwen3.5:9b",
    )
    monkeypatch.setenv(
        "SOFIA_COGNITION_SECONDARY_MODEL",
        "huihui_ai/qwen3.5-abliterated:4B",
    )
    monkeypatch.setenv(
        "SOFIA_COGNITION_PRIMARY_CONTEXT_SIZE",
        "16000",
    )
    monkeypatch.setenv(
        "SOFIA_COGNITION_SECONDARY_CONTEXT_SIZE",
        "8192",
    )

    configuration = create_default_configuration()

    assert configuration.routing is not None
    assert configuration.routing.enabled is True
    assert configuration.routing.primary is not None
    assert configuration.routing.secondary is not None
    assert configuration.routing.primary.model == "qwen3.5:9b"
    assert configuration.routing.primary.context_size == 16000
    assert (
        configuration.routing.secondary.model
        == "huihui_ai/qwen3.5-abliterated:4B"
    )
    assert configuration.routing.secondary.context_size == 8192


def test_default_configuration_keeps_routing_off_without_flag(monkeypatch):
    monkeypatch.delenv(
        "SOFIA_COGNITION_ROUTING_ENABLED",
        raising=False,
    )

    configuration = create_default_configuration()

    assert configuration.routing is None


def test_composition_builds_router_for_test_llm_models():
    routing = CognitiveRoutingConfiguration(
        enabled=True,
        primary=ProviderConfiguration(
            provider="test-llm",
            model="primary-model",
        ),
        secondary=ProviderConfiguration(
            provider="test-llm",
            model="secondary-model",
        ),
    )
    configuration = SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        state_path=Path("sofia.db"),
        provider=ProviderConfiguration(
            provider="test-llm",
            model="legacy-model",
        ),
        filesystem_root=Path("."),
        routing=routing,
    )

    engine = _create_cognitive_engine(configuration)

    assert isinstance(engine, RoutingCognitiveEngine)
    assert (
        engine.registry.primary.configuration.model
        == "primary-model"
    )
    assert (
        engine.registry.secondary.configuration.model
        == "secondary-model"
    )


def test_invalid_routing_flag_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "SOFIA_COGNITION_ROUTING_ENABLED",
        "banana",
    )

    with pytest.raises(ValueError, match="boolean flag"):
        create_default_configuration()



def test_tool_enabled_primary_failure_does_not_fall_back_to_secondary():
    tool = CognitiveToolDefinition(
        name="ops.execute",
        description="Execute an authorized operation.",
        parameters={"type": "object"},
    )
    primary = QueueEngine(
        CognitiveEngineError("primary failed")
    )
    secondary = QueueEngine(
        CognitiveResponse(content="secondary must not run")
    )
    engine = RoutingCognitiveEngine(
        registry(primary, secondary)
    )

    with pytest.raises(CognitiveEngineError, match="primary failed"):
        engine.respond(
            request("Run this operation.", tools=(tool,))
        )

    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_reviewed_interaction_context_routes_to_primary():
    primary = QueueEngine(CognitiveResponse(content="grounded"))
    secondary = QueueEngine()
    engine = RoutingCognitiveEngine(registry(primary, secondary))
    value = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="TRUSTED INTERACTION INTERPRETATION\n{}",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="*pats your head*",
            ),
        ),
    )

    response = engine.respond(value)

    assert response.content == "grounded"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.STANDARD
    assert len(primary.requests) == 1
    assert len(secondary.requests) == 0


def test_incomplete_secondary_response_falls_back_to_primary():
    secondary = QueueEngine(CognitiveResponse(content="I"))
    primary = QueueEngine(CognitiveResponse(content="complete fallback"))
    engine = RoutingCognitiveEngine(registry(primary, secondary))

    response = engine.respond(request("hello"))

    assert response.content == "complete fallback"
    assert len(secondary.requests) == 1
    assert len(primary.requests) == 1


def test_verify_precedes_reviewed_interaction_standard_routing():
    primary = QueueEngine(
        CognitiveResponse(content="draft"),
        CognitiveResponse(content="final"),
    )
    secondary = QueueEngine(CognitiveResponse(content="critique"))
    engine = RoutingCognitiveEngine(registry(primary, secondary))
    value = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="TRUSTED INTERACTION INTERPRETATION\n{}",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Please verify your answer about this interaction.",
            ),
        ),
    )

    response = engine.respond(value)

    assert response.content == "final"
    assert engine.last_decision is not None
    assert engine.last_decision.route is CognitiveRoute.VERIFY
    assert len(primary.requests) == 2
    assert len(secondary.requests) == 1


class RemoteInferenceStub:
    def infer(self, node_id, provider, request):
        return CognitiveResponse(content="remote")


def test_default_configuration_keeps_fleet_cognition_off(monkeypatch):
    monkeypatch.delenv("SOFIA_COGNITION_FLEET_ENABLED", raising=False)
    configuration = create_default_configuration()
    assert configuration.fleet_cognition.enabled is False


def test_default_configuration_parses_fleet_cognition_policy(monkeypatch):
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_ENABLED", "1")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_LOCAL_FALLBACK", "1")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_GPU_REQUIRED", "1")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_MIN_RAM_BYTES", "123")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_MIN_VRAM_BYTES", "456")
    monkeypatch.setenv(
        "SOFIA_COGNITION_FLEET_ALLOWED_HOST_IDS",
        "alpha,beta,alpha",
    )

    configuration = create_default_configuration()

    policy = configuration.fleet_cognition
    assert policy.enabled is True
    assert policy.local_fallback is True
    assert policy.gpu_required is True
    assert policy.min_ram_bytes == 123
    assert policy.min_vram_bytes == 456
    assert policy.allowed_host_ids == ("alpha", "beta")


def test_composition_wraps_both_routed_roles_for_fleet_cognition(tmp_path):
    state = tmp_path / "sofia.db"
    routing = CognitiveRoutingConfiguration(
        enabled=True,
        primary=ProviderConfiguration(
            provider="test-llm",
            model="primary-model",
        ),
        secondary=ProviderConfiguration(
            provider="test-llm",
            model="secondary-model",
        ),
    )
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=state,
        provider=ProviderConfiguration(
            provider="test-llm",
            model="legacy-model",
        ),
        filesystem_root=tmp_path,
        routing=routing,
        fleet_cognition=FleetCognitionConfiguration(enabled=True),
    )
    ops = OpsToolService(
        state,
        state_plane=SQLiteStatePlane(state),
    )

    engine = _create_cognitive_engine(
        configuration,
        ops_service=ops,
        local_host_id="local-host",
        remote_inference_client=RemoteInferenceStub(),
    )

    assert isinstance(engine, RoutingCognitiveEngine)
    assert isinstance(engine.registry.primary, FleetPlacedCognitiveEngine)
    assert isinstance(engine.registry.secondary, FleetPlacedCognitiveEngine)
    assert engine.registry.primary.workload_id == "cognition-primary"
    assert engine.registry.secondary.workload_id == "cognition-secondary"


def test_fleet_cognition_fails_closed_without_remote_transport(tmp_path):
    state = tmp_path / "sofia.db"
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=state,
        provider=ProviderConfiguration(
            provider="test-llm",
            model="primary-model",
        ),
        filesystem_root=tmp_path,
        fleet_cognition=FleetCognitionConfiguration(enabled=True),
    )
    ops = OpsToolService(
        state,
        state_plane=SQLiteStatePlane(state),
    )

    with pytest.raises(ValueError, match="pinned-mTLS"):
        _create_cognitive_engine(
            configuration,
            ops_service=ops,
            local_host_id="local-host",
            remote_inference_client=None,
        )
