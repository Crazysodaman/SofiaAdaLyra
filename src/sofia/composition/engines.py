"""Compose local, lifecycle-managed and fleet-routed cognitive engines."""
from sofia.cognition.activity import CognitiveModelActivityStore
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.fleet_engine import (
    FleetCognitionPolicy,
    FleetPlacedCognitiveEngine,
)
from sofia.cognition.model_lifecycle import (
    CognitiveModelRole,
    LifecycleManagedCognitiveEngine,
    ModelLifecycleManager,
)
from sofia.cognition.providers.factory import create_llm_provider
from sofia.cognition.routing import (
    CognitiveEngineRegistry,
    RoutingCognitiveEngine,
)
from sofia.cognition.rules import RuleEngine
from sofia.cognition.test_engine import TestCognitiveEngine
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import SofiaConfiguration
from sofia.integrations.ollama import OllamaAdapter
from sofia.ops.capability import OpsToolService
from sofia.ops.local_telemetry import collect_local_telemetry
from sofia.ops.activity import ActivityMode


def _create_llm_engine(
    provider_configuration,
    *,
    lifecycle: ModelLifecycleManager | None = None,
    role: CognitiveModelRole | None = None,
):
    provider = create_llm_provider(
        provider_configuration,
        keep_alive=(
            lifecycle.policy.keep_alive
            if lifecycle is not None
            and provider_configuration.provider == "ollama"
            else None
        ),
    )
    engine = LLMCognitiveEngine(
        configuration=provider_configuration,
        provider=provider,
    )
    if (
        lifecycle is not None
        and role is not None
        and provider_configuration.provider == "ollama"
    ):
        return LifecycleManagedCognitiveEngine(
            delegate=engine,
            lifecycle=lifecycle,
            role=role,
        )
    return engine


def create_model_lifecycle(
    configuration: SofiaConfiguration,
    *,
    ops_service: OpsToolService | None = None,
    local_host_id: str | None = None,
) -> ModelLifecycleManager | None:
    if not configuration.model_lifecycle.enabled:
        return None
    selection = CognitiveModelSelection.from_configuration(configuration)
    if not any(
        provider.provider == "ollama"
        for provider in selection.providers
    ):
        return None
    gaming_observer = None
    if ops_service is not None and local_host_id:
        def observe_gaming() -> bool | None:
            mode = ops_service.activity.state(local_host_id).effective
            if mode is ActivityMode.UNKNOWN:
                return None
            return mode is ActivityMode.GAMING
        gaming_observer = observe_gaming
    return ModelLifecycleManager(
        selection=selection,
        policy=configuration.model_lifecycle,
        backend=OllamaAdapter(),
        resource_observer=collect_local_telemetry,
        gaming_observer=gaming_observer,
    )


def _fleet_wrap_cognitive_engine(
    local,
    *,
    provider_configuration,
    configuration: SofiaConfiguration,
    ops_service: OpsToolService | None,
    local_host_id: str | None,
    remote_inference_client,
    workload_id: str,
):
    policy = configuration.fleet_cognition
    if not policy.enabled:
        return local
    if ops_service is None:
        raise ValueError("enabled Fleet cognition requires OPS service")
    if not isinstance(local_host_id, str) or not local_host_id.strip():
        raise ValueError("enabled Fleet cognition requires local host identity")
    if remote_inference_client is None:
        raise ValueError(
            "enabled Fleet cognition requires configured pinned-mTLS remote transport"
        )
    return FleetPlacedCognitiveEngine(
        local=local,
        provider=provider_configuration,
        ops=ops_service,
        local_host_id=local_host_id,
        remote_infer=remote_inference_client.infer,
        remote_prepare=remote_inference_client.ensure_model_available,
        policy=FleetCognitionPolicy(
            enabled=True,
            local_fallback=policy.local_fallback,
            min_ram_bytes=policy.min_ram_bytes,
            min_vram_bytes=policy.min_vram_bytes,
            gpu_required=policy.gpu_required,
            auto_provision_models=policy.auto_provision_models,
            allowed_host_ids=policy.allowed_host_ids,
            denied_host_ids=policy.denied_host_ids,
        ),
        workload_id=workload_id,
    )


def create_cognitive_engine(
    configuration: SofiaConfiguration,
    *,
    lifecycle: ModelLifecycleManager | None = None,
    ops_service: OpsToolService | None = None,
    local_host_id: str | None = None,
    remote_inference_client=None,
):
    routing = configuration.routing
    if routing is not None and routing.enabled:
        primary_configuration = routing.primary
        secondary_configuration = routing.secondary
        if (
            primary_configuration is None
            or secondary_configuration is None
        ):
            raise ValueError(
                "enabled cognitive routing requires primary and secondary "
                "provider configurations"
            )
        supported = {"ollama", "test-llm"}
        if primary_configuration.provider not in supported:
            raise ValueError(
                "routing primary provider must be ollama or test-llm"
            )
        if secondary_configuration.provider not in supported:
            raise ValueError(
                "routing secondary provider must be ollama or test-llm"
            )

        primary_engine = _fleet_wrap_cognitive_engine(
            _create_llm_engine(
                primary_configuration,
                lifecycle=lifecycle,
                role=CognitiveModelRole.PRIMARY,
            ),
            provider_configuration=primary_configuration,
            configuration=configuration,
            ops_service=ops_service,
            local_host_id=local_host_id,
            remote_inference_client=remote_inference_client,
            workload_id="cognition-primary",
        )
        secondary_engine = _fleet_wrap_cognitive_engine(
            _create_llm_engine(
                secondary_configuration,
                lifecycle=lifecycle,
                role=CognitiveModelRole.SECONDARY,
            ),
            provider_configuration=secondary_configuration,
            configuration=configuration,
            ops_service=ops_service,
            local_host_id=local_host_id,
            remote_inference_client=remote_inference_client,
            workload_id="cognition-secondary",
        )
        registry = CognitiveEngineRegistry(
            primary=primary_engine,
            secondary=secondary_engine,
        )
        activity_store = CognitiveModelActivityStore(
            configuration.state_path
        )
        activity_store.clear_stale_busy()
        return RoutingCognitiveEngine(
            registry=registry,
            verify_enabled=routing.verify_enabled,
            parallel_enabled=routing.parallel_enabled,
            fallback_enabled=routing.fallback_enabled,
            activity_store=activity_store,
        )

    if configuration.provider.provider == "test":
        return TestCognitiveEngine(
            configuration=configuration.provider
        )

    if configuration.provider.provider == "rule":
        return RuleEngine()

    if configuration.provider.provider in {"test-llm", "ollama"}:
        local_engine = _create_llm_engine(
            configuration.provider,
            lifecycle=lifecycle,
            role=CognitiveModelRole.PRIMARY,
        )
        return _fleet_wrap_cognitive_engine(
            local_engine,
            provider_configuration=configuration.provider,
            configuration=configuration,
            ops_service=ops_service,
            local_host_id=local_host_id,
            remote_inference_client=remote_inference_client,
            workload_id="cognition-primary",
        )

    raise ValueError(
        f"Unknown cognitive provider: "
        f"{configuration.provider.provider}"
    )
