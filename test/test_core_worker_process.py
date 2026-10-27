from datetime import datetime, timedelta, timezone
from hashlib import sha256
import multiprocessing
import os

import pytest

from sofia.core.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
    CognitiveToolDefinition,
)
from sofia.core.cognition.provider import LLMProvider, LLMProviderError
from sofia.core.cognition.providers.test_provider import TestLLMProvider
from sofia.core.cognition.fleet_engine import FleetPlacedCognitiveEngine
from sofia.core.cognition.routing import RoutingCognitiveEngine
from sofia.platform.core_worker import (
    CoreEngineProcessSpec, CoreWorkerController, CoreWorkerCognitiveEngine,
    CoreWorkerError,
    CoreWorkerRuntimeBackend,
    PlatformProviderBinding,
    installed_core_release_digest,
)
from sofia.platform.inference_worker import (
    InferenceProcessOwner, InferenceProviderProcess, InferenceWorkerError,
)
from sofia.platform.composition.engines import create_cognitive_engine
from sofia.platform.composition.root import compose
from sofia.platform.config.model import (
    CognitiveRoutingConfiguration, CoreWorkerConfiguration,
    FleetCognitionConfiguration, ProviderConfiguration, SofiaConfiguration,
)
from sofia.platform.ops.capability import OpsToolService
from sofia.platform.run import ComponentGenerationStore, GenerationState, LocalRunLeaseStore
from sofia.platform.run import ComponentRuntimeSupervisor, ComponentSpec
from sofia.platform.run.components import ComponentKind as SupervisedComponentKind
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.sdk import decode_request, encode_request
from sofia.sdk import (
    AuthorityProjection, ComponentEndpoint, ComponentKind,
    ComponentRequestEnvelope, ProtocolVersion,
)


def build(canonical_state_path, tmp_path, component_id="core.sofia"):
    now = datetime.now(timezone.utc)
    leases = LocalRunLeaseStore(canonical_state_path)
    lease = leases.acquire(
        owner_id="platform:iso03-test", now=now, ttl_seconds=300,
    ).lease
    assert lease is not None
    generations = ComponentGenerationStore(
        state_path=canonical_state_path, lease_store=leases,
    )
    controller = CoreWorkerController(
        generations=generations, lease=lease,
        platform_instance_id="platform:test", core_identity_id="core:sofia",
        component_id=component_id, runtime_dir=tmp_path / "runtime",
        response_timeout=timedelta(seconds=10),
    )
    return now, generations, controller


def request():
    return CognitiveRequest(
        messages=(
            CognitiveMessage(CognitiveRole.SYSTEM, "Identity: Sofía; memory marker: fox-lab"),
            CognitiveMessage(CognitiveRole.USER, "What is your name?"),
        ),
        tools=(CognitiveToolDefinition(
            "inspect.read_only", "Read an already authorized projection.",
            {"type": "object", "properties": {"target": {"type": "string"}}},
        ),),
        allow_tools=True,
        capability_allowlist=("inspect.read_only",),
        route_hint="standard",
    )


def bind_test_providers(controller, primary, secondary=None):
    response = CognitiveResponse("platform-provider-response")
    bindings = {
        "primary": PlatformProviderBinding(
            primary, TestLLMProvider(response=response),
        )
    }
    if secondary is not None:
        bindings["secondary"] = PlatformProviderBinding(
            secondary, TestLLMProvider(response=response),
        )
    controller.bind_providers(bindings)


def test_codec_preserves_identity_memory_and_tool_proposals_exactly():
    original = request()
    assert decode_request(encode_request(original)) == original


def test_process_spec_round_trips_exact_dual_model_identity():
    primary = ProviderConfiguration(provider="ollama", model="owner/deep:sha")
    secondary = ProviderConfiguration(provider="ollama", model="owner/fast:sha")
    spec = CoreEngineProcessSpec(
        "provider", provider=primary, secondary_provider=secondary,
        expected_runtime_digest="a" * 64,
    )

    assert CoreEngineProcessSpec.from_payload(spec.to_payload()) == spec
    with pytest.raises(ValueError, match="secondary provider"):
        CoreEngineProcessSpec("rule", secondary_provider=secondary)


class _PlatformPidProvider(LLMProvider):
    def respond(self, cognitive_request):
        assert cognitive_request == request()
        return CognitiveResponse(f"provider-pid:{os.getpid()}")


def test_provider_executes_in_platform_not_core_process(
    canonical_state_path, tmp_path,
):
    now, _, controller = build(canonical_state_path, tmp_path)
    configuration = ProviderConfiguration(
        provider="test-llm", model="platform-owned-model"
    )
    controller.bind_providers({
        "primary": PlatformProviderBinding(
            configuration, _PlatformPidProvider(),
        )
    })
    health = controller.start(
        release_digest=sha256(b"platform-provider-boundary").hexdigest(),
        spec=CoreEngineProcessSpec("provider", provider=configuration),
        now=now,
    )

    response = CoreWorkerCognitiveEngine(
        controller, configuration=configuration,
    ).respond(request())

    assert health.pid != os.getpid()
    assert response.content == f"provider-pid:{os.getpid()}"
    controller.shutdown(now=now + timedelta(seconds=1))


def test_inference_adapter_runs_in_independent_authenticated_process(tmp_path):
    configuration = ProviderConfiguration(
        provider="test-llm", model="isolated-provider-model"
    )
    release_digest = installed_core_release_digest()
    process = InferenceProviderProcess(
        configuration=configuration,
        role="primary",
        release_digest=release_digest,
        platform_instance_id="platform:test",
        response_timeout_seconds=5,
    )

    health = process.start(
        endpoint=ComponentEndpoint(
            "inference.primary.test", ComponentKind.INFERENCE,
            release_digest, 1, "platform:test",
        ),
        epoch=7,
    )

    assert health.pid == process.pid
    assert health.pid != os.getpid()
    assert health.ready and health.accepting
    assert health.role == "primary"
    assert health.epoch == 7
    with pytest.raises(LLMProviderError, match="isolated inference"):
        process.respond(request())
    assert process.health().pid == health.pid
    process.close()
    assert process.pid is None


def test_inference_worker_identity_binds_exact_provider_endpoint():
    from sofia.platform.inference_worker.process import _configuration_digest

    configuration = ProviderConfiguration(
        provider="test-llm", model="endpoint-bound-model"
    )

    assert _configuration_digest(
        configuration, "http://127.0.0.1:11434"
    ) != _configuration_digest(
        configuration, "https://gpu.example:11434"
    )


def test_inference_worker_independently_rejects_wrong_release_bytes():
    process = InferenceProviderProcess(
        configuration=ProviderConfiguration(
            provider="test-llm", model="forged-release-model"
        ),
        role="primary",
        release_digest="0" * 64,
        platform_instance_id="platform:test",
        response_timeout_seconds=5,
    )

    with pytest.raises(Exception, match="readiness identity"):
        process.start(
            endpoint=ComponentEndpoint(
                "inference.primary.forged", ComponentKind.INFERENCE,
                "0" * 64, 1, "platform:test",
            ),
            epoch=3,
        )

    assert process.pid is None


def test_inference_restart_blocks_unreconciled_active_generation(
    canonical_state_path,
):
    digest = installed_core_release_digest()
    configuration = ProviderConfiguration(
        provider="test-llm", model="restart-fenced-model"
    )
    first = InferenceProcessOwner(
        state_path=canonical_state_path,
        process=InferenceProviderProcess(
            configuration=configuration, role="primary",
            release_digest=digest, platform_instance_id="platform:test",
            response_timeout_seconds=5,
        ),
        component_id="inference.primary.restart-test",
    )
    health = first.start()
    endpoint = first.endpoint
    assert endpoint is not None and first.generations.is_active(endpoint)
    assert health.generation == endpoint.generation

    first._stop.set()
    if first._thread is not None:
        first._thread.join(2)
    first.process.close(force=True)
    first.lease_store.release(first.lease, now=datetime.now(timezone.utc))
    replacement = InferenceProcessOwner(
        state_path=canonical_state_path,
        process=InferenceProviderProcess(
            configuration=configuration, role="primary",
            release_digest=digest, platform_instance_id="platform:test",
            response_timeout_seconds=5,
        ),
        component_id="inference.primary.restart-test",
    )

    with pytest.raises(InferenceWorkerError, match="explicit reconciliation"):
        replacement.start()

    assert replacement.pid is None
    assert replacement.generations.active_for_component(
        "inference.primary.restart-test"
    ) == endpoint


def test_draining_inference_generation_cannot_dispatch(
    canonical_state_path,
):
    digest = installed_core_release_digest()
    configuration = ProviderConfiguration(
        provider="test-llm", model="draining-model"
    )
    owner = InferenceProcessOwner(
        state_path=canonical_state_path,
        process=InferenceProviderProcess(
            configuration=configuration, role="primary",
            release_digest=digest, platform_instance_id="platform:test",
            response_timeout_seconds=5,
        ),
        component_id="inference.primary.draining-test",
    )
    owner.start()
    endpoint = owner.endpoint
    assert endpoint is not None
    owner.generations.begin_drain(
        endpoint, lease=owner.lease, now=datetime.now(timezone.utc),
        reason="test external fence",
    )

    with pytest.raises(LLMProviderError, match="authority"):
        owner.respond(request())

    owner.close()
    assert owner.generations.state(endpoint) is GenerationState.QUARANTINED
    assert owner.pid is None


def test_provider_worker_start_fails_closed_without_exact_platform_binding(
    canonical_state_path, tmp_path,
):
    now, generations, controller = build(canonical_state_path, tmp_path)
    configuration = ProviderConfiguration(
        provider="test-llm", model="unbound-model"
    )

    with pytest.raises(CoreWorkerError, match="exact Platform provider"):
        controller.start(
            release_digest=sha256(b"unbound-provider").hexdigest(),
            spec=CoreEngineProcessSpec("provider", provider=configuration),
            now=now,
        )

    assert generations.active_for_core_identity("core:sofia") is None
    assert controller.pid is None


def test_platform_provider_failure_quarantines_core_without_retry(
    canonical_state_path, tmp_path,
):
    now, generations, controller = build(canonical_state_path, tmp_path)
    configuration = ProviderConfiguration(
        provider="test-llm", model="failing-model"
    )
    provider = TestLLMProvider(error=LLMProviderError("provider unavailable"))
    controller.bind_providers({
        "primary": PlatformProviderBinding(configuration, provider),
    })
    health = controller.start(
        release_digest=sha256(b"failing-platform-provider").hexdigest(),
        spec=CoreEngineProcessSpec("provider", provider=configuration),
        now=now,
    )

    with pytest.raises(Exception, match="failed or became uncertain"):
        CoreWorkerCognitiveEngine(
            controller, configuration=configuration,
        ).respond(request())

    assert provider.received_request == request()
    assert generations.state(health.endpoint) is GenerationState.QUARANTINED
    assert controller.pid is None


def test_composition_routes_both_roles_through_one_generation_fenced_worker(
    canonical_state_path, tmp_path,
):
    now, _, controller = build(canonical_state_path, tmp_path)
    primary = ProviderConfiguration(provider="test-llm", model="deep-model")
    secondary = ProviderConfiguration(provider="test-llm", model="fast-model")
    bind_test_providers(controller, primary, secondary)
    controller.start(
        release_digest=sha256(b"dual-model-worker").hexdigest(),
        spec=CoreEngineProcessSpec(
            "provider", provider=primary, secondary_provider=secondary,
        ),
        now=now,
    )
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=primary,
        filesystem_root=tmp_path,
        routing=CognitiveRoutingConfiguration(
            enabled=True, primary=primary, secondary=secondary,
        ),
    )

    engine = create_cognitive_engine(
        configuration, core_worker_controller=controller,
    )

    assert isinstance(engine, RoutingCognitiveEngine)
    assert isinstance(engine.registry.primary, CoreWorkerCognitiveEngine)
    assert isinstance(engine.registry.secondary, CoreWorkerCognitiveEngine)
    assert engine.registry.primary.controller is controller
    assert engine.registry.secondary.controller is controller
    assert engine.registry.primary.role == "primary"
    assert engine.registry.secondary.role == "secondary"
    assert engine.registry.primary.configuration == primary
    assert engine.registry.secondary.configuration == secondary
    controller.shutdown(now=now + timedelta(seconds=1))


class _RemoteInference:
    def ensure_model_available(self, node_id, provider, auto_provision):
        return None

    def infer(self, node_id, provider, cognitive_request):
        raise AssertionError("composition must not dispatch during construction")


def test_fleet_placement_wraps_each_isolated_core_role_without_local_fallback(
    canonical_state_path, tmp_path,
):
    now, _, controller = build(canonical_state_path, tmp_path)
    primary = ProviderConfiguration(provider="test-llm", model="deep-model")
    secondary = ProviderConfiguration(provider="test-llm", model="fast-model")
    bind_test_providers(controller, primary, secondary)
    controller.start(
        release_digest=sha256(b"fleet-dual-worker").hexdigest(),
        spec=CoreEngineProcessSpec(
            "provider", provider=primary, secondary_provider=secondary,
        ),
        now=now,
    )
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=primary,
        filesystem_root=tmp_path,
        routing=CognitiveRoutingConfiguration(
            enabled=True, primary=primary, secondary=secondary,
        ),
        fleet_cognition=FleetCognitionConfiguration(
            enabled=True, local_fallback=False,
        ),
    )
    ops = OpsToolService(
        canonical_state_path,
        state_plane=SQLiteStatePlane(canonical_state_path),
    )

    engine = create_cognitive_engine(
        configuration, ops_service=ops, local_host_id="local-host",
        remote_inference_client=_RemoteInference(),
        core_worker_controller=controller,
    )

    assert isinstance(engine, RoutingCognitiveEngine)
    for role, expected in (
        (engine.registry.primary, "primary"),
        (engine.registry.secondary, "secondary"),
    ):
        assert isinstance(role, FleetPlacedCognitiveEngine)
        assert role.policy.local_fallback is False
        assert isinstance(role.local, CoreWorkerCognitiveEngine)
        assert role.local.role == expected
        assert role.local.controller is controller
    controller.shutdown(now=now + timedelta(seconds=1))


def test_worker_spec_must_match_both_configured_model_roles(
    canonical_state_path, tmp_path,
):
    now, _, controller = build(canonical_state_path, tmp_path)
    primary = ProviderConfiguration(provider="test-llm", model="deep-model")
    configured_secondary = ProviderConfiguration(
        provider="test-llm", model="fast-model"
    )
    bind_test_providers(
        controller, primary,
        ProviderConfiguration(provider="test-llm", model="other-model"),
    )
    controller.start(
        release_digest=sha256(b"wrong-secondary").hexdigest(),
        spec=CoreEngineProcessSpec(
            "provider", provider=primary,
            secondary_provider=ProviderConfiguration(
                provider="test-llm", model="other-model"
            ),
        ),
        now=now,
    )
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=primary,
        filesystem_root=tmp_path,
        routing=CognitiveRoutingConfiguration(
            enabled=True, primary=primary, secondary=configured_secondary,
        ),
    )

    with pytest.raises(ValueError, match="does not match selected provider"):
        create_cognitive_engine(
            configuration, core_worker_controller=controller,
        )
    assert controller.health().ready
    controller.shutdown(now=now + timedelta(seconds=1))


def test_real_process_replacement_keeps_platform_and_continuity(canonical_state_path, tmp_path):
    now, generations, controller = build(canonical_state_path, tmp_path)
    platform_pid = os.getpid()
    first = controller.start(
        release_digest=sha256(b"core-v1").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    first_process = controller._active
    assert first_process is not None and first.pid != platform_pid
    assert controller.health().ready
    engine = CoreWorkerCognitiveEngine(controller)
    assert engine.respond(request()).content == "I am Sofía Ada Lyra."

    second = controller.replace(
        release_digest=sha256(b"core-v2").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now + timedelta(seconds=1),
    )
    assert os.getpid() == platform_pid
    assert second.pid != first.pid
    assert first_process.alive is False
    assert generations.state(first.endpoint) is GenerationState.RETIRED
    assert generations.is_active(first.endpoint) is False
    assert generations.is_active(second.endpoint) is True
    assert engine.respond(request()).content == "I am Sofía Ada Lyra."

    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=ProviderConfiguration(provider="rule", model="rule-engine"),
        filesystem_root=tmp_path,
    )
    composed = create_cognitive_engine(
        configuration, core_worker_controller=controller,
    )
    assert isinstance(composed, CoreWorkerCognitiveEngine)
    assert composed.respond(request()).content == "I am Sofía Ada Lyra."
    runtime = compose(configuration, core_worker_controller=controller)
    assert isinstance(runtime.cognitive_system.engine, CoreWorkerCognitiveEngine)
    assert runtime.cognitive_system.engine.respond(request()).content == "I am Sofía Ada Lyra."
    runtime._close_runtime_resources()
    controller.shutdown(now=now + timedelta(seconds=2))


def test_duplicate_core_identity_with_different_component_id_is_denied(canonical_state_path, tmp_path):
    now, generations, first = build(canonical_state_path, tmp_path, "core.sofia")
    first.start(
        release_digest=sha256(b"one").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    second = CoreWorkerController(
        generations=generations, lease=first.lease,
        platform_instance_id="platform:test", core_identity_id="core:sofia",
        component_id="core.alias", runtime_dir=tmp_path / "runtime-two",
    )
    with pytest.raises(RuntimeError, match="Core identity"):
        second.start(
            release_digest=sha256(b"two").hexdigest(),
            spec=CoreEngineProcessSpec("rule"), now=now + timedelta(seconds=1),
        )
    assert second.pid is None
    assert first.health().ready
    first.shutdown(now=now + timedelta(seconds=2))


def test_crash_and_cancel_fence_old_generation_without_replay(canonical_state_path, tmp_path):
    now, generations, controller = build(canonical_state_path, tmp_path)
    health = controller.start(
        release_digest=sha256(b"crash").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    process = controller._active
    assert process is not None and process._process is not None
    process._process.terminate()
    process._process.join(5)
    with pytest.raises(CoreWorkerError):
        controller.health()
    assert generations.state(health.endpoint) is GenerationState.QUARANTINED
    assert generations.is_active(health.endpoint) is False
    with pytest.raises(Exception):
        CoreWorkerCognitiveEngine(controller).respond(request())

    replacement = controller.start(
        release_digest=sha256(b"after-crash").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now + timedelta(seconds=1),
    )
    controller.cancel(now=now + timedelta(seconds=2), reason="operator cancel")
    assert generations.state(replacement.endpoint) is GenerationState.QUARANTINED
    assert controller.pid is None


def test_bad_protocol_and_response_timeout_quarantine_worker(canonical_state_path, tmp_path):
    now, generations, controller = build(canonical_state_path, tmp_path)
    active = controller.start(
        release_digest=sha256(b"bad-protocol").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    process = controller._active
    assert process is not None
    payload = encode_request(request())
    bad = ComponentRequestEnvelope(
        protocol=ProtocolVersion(2, 0),
        request_id="request:bad-protocol", correlation_id="correlation:bad",
        idempotency_key="idempotency:bad",
        source=ComponentEndpoint(
            "platform.host", ComponentKind.PLATFORM, active.endpoint.release_digest,
            controller.lease.epoch, "platform:test",
        ),
        destination=active.endpoint,
        authority=AuthorityProjection(
            "system:platform", "system:core", "system",
            f"run:{controller.lease.owner_id}:{controller.lease.epoch}",
            ("cognition.respond",), controller.lease.expires_at,
        ),
        payload_type="sofia.core.cognition.request.v1",
        payload_digest=sha256(payload).hexdigest(), created_at=now,
        deadline=min(now + timedelta(seconds=5), controller.lease.expires_at),
    )
    with pytest.raises(CoreWorkerError):
        process.respond(envelope=bad, request=request(), timeout=5)
    controller.cancel(now=now + timedelta(seconds=1), reason="bad protocol")
    assert generations.state(active.endpoint) is GenerationState.QUARANTINED

    _, generations2, slow = build(canonical_state_path, tmp_path / "slow", "core.sofia.slow")
    slow.response_timeout = timedelta(milliseconds=50)
    delayed = slow.start(
        release_digest=sha256(b"slow").hexdigest(),
        spec=CoreEngineProcessSpec("test", test_delay_seconds=1),
        now=now + timedelta(seconds=2),
    )
    with pytest.raises(Exception):
        CoreWorkerCognitiveEngine(slow).respond(request())
    assert generations2.state(delayed.endpoint) is GenerationState.QUARANTINED


def test_interrupted_drain_quarantines_old_before_replacement(canonical_state_path, tmp_path):
    now, generations, controller = build(canonical_state_path, tmp_path)
    old = controller.start(
        release_digest=sha256(b"old-crash").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    process = controller._active
    assert process is not None and process._process is not None
    process._process.terminate()
    process._process.join(5)
    new = controller.replace(
        release_digest=sha256(b"new-after-interrupted-drain").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now + timedelta(seconds=1),
    )
    assert generations.state(old.endpoint) is GenerationState.QUARANTINED
    assert generations.is_active(new.endpoint)
    controller.shutdown(now=now + timedelta(seconds=2))


def test_restart_reconciliation_never_blindly_reconnects_or_replays(canonical_state_path, tmp_path):
    now, generations, original = build(canonical_state_path, tmp_path)
    old = original.start(
        release_digest=sha256(b"before-restart").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now,
    )
    process = original._active
    assert process is not None and process._process is not None
    process._process.terminate()
    process._process.join(5)

    recovered = CoreWorkerController(
        generations=ComponentGenerationStore(
            state_path=canonical_state_path,
            lease_store=generations.lease_store,
        ),
        lease=original.lease, platform_instance_id="platform:test",
        core_identity_id="core:sofia", component_id="core.sofia",
        runtime_dir=tmp_path / "recovered",
    )
    with pytest.raises(CoreWorkerError, match="unknown"):
        recovered.reconcile_startup(observe_running=lambda endpoint: None, now=now)
    assert generations.is_active(old.endpoint)
    assert recovered.reconcile_startup(
        observe_running=lambda endpoint: False,
        now=now + timedelta(seconds=1),
    ) == "prior_stopped_generation_quarantined"
    assert generations.state(old.endpoint) is GenerationState.QUARANTINED
    new = recovered.start(
        release_digest=sha256(b"after-restart").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), now=now + timedelta(seconds=2),
    )
    assert generations.is_active(new.endpoint)
    recovered.shutdown(now=now + timedelta(seconds=3))


def test_existing_component_supervisor_owns_real_core_process(canonical_state_path, tmp_path):
    now, _, controller = build(canonical_state_path, tmp_path)
    supervisor = ComponentRuntimeSupervisor(
        state_path=canonical_state_path,
        lease_store=controller.generations.lease_store,
    )
    backend = CoreWorkerRuntimeBackend(
        controller=controller, release_digest=sha256(b"supervised").hexdigest(),
        spec=CoreEngineProcessSpec("rule"), clock=lambda: now,
    )
    supervisor.register(
        ComponentSpec("core.sofia", SupervisedComponentKind.CORE),
        backend, now=now,
    )
    action = supervisor.start_component(
        "core.sofia", lease=controller.lease, now=now,
    )
    assert action.action == "started"
    assert action.status.health.value == "healthy"
    pid = controller.pid
    assert pid is not None and pid != os.getpid()
    stopped = supervisor.stop_component(
        "core.sofia", lease=controller.lease,
        now=now + timedelta(seconds=1), reason="test stop",
    )
    assert stopped.action == "stopped"
    assert controller.pid is None


def test_startup_deadline_quarantines_generation_and_leaves_no_child(
    canonical_state_path, tmp_path,
):
    now, generations, base = build(
        canonical_state_path, tmp_path, "core.startup-timeout"
    )
    controller = CoreWorkerController(
        generations=generations, lease=base.lease,
        platform_instance_id="platform:test", core_identity_id="core:startup-timeout",
        component_id="core.startup-timeout",
        runtime_dir=tmp_path / "startup-timeout-runtime",
        response_timeout=timedelta(seconds=5),
        startup_timeout=timedelta(seconds=1),
    )
    digest = sha256(b"startup-timeout").hexdigest()
    endpoint = ComponentEndpoint(
        "core.startup-timeout", ComponentKind.CORE, digest, 1,
        "platform:test", "core:startup-timeout",
    )

    with pytest.raises(CoreWorkerError, match="attestation/readiness deadline"):
        controller.start(
            release_digest=digest,
            spec=CoreEngineProcessSpec(
                "test", test_startup_delay_seconds=2,
            ),
            now=now,
        )

    assert controller.pid is None
    assert generations.state(endpoint) is GenerationState.QUARANTINED
    assert generations.active_for_core_identity("core:startup-timeout") is None
    assert all(
        child.name != "sofia-core-1" or not child.is_alive()
        for child in multiprocessing.active_children()
    )


def test_production_composition_owns_configured_core_process(canonical_state_path, tmp_path):
    digest = installed_core_release_digest()
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=ProviderConfiguration(provider="rule", model="rule-engine"),
        filesystem_root=tmp_path,
        core_worker=CoreWorkerConfiguration(
            enabled=True, release_digest=digest,
            platform_instance_id="platform:composition-test",
        ),
    )

    runtime = compose(configuration)
    engine = runtime.cognitive_system.engine
    assert isinstance(engine, CoreWorkerCognitiveEngine)
    pid = engine.controller.pid
    endpoint = engine.controller.endpoint
    assert pid is not None and pid != os.getpid() and endpoint is not None
    assert engine.respond(request()).content == "I am Sofía Ada Lyra."

    lease_store = engine.controller.generations.lease_store
    runtime._close_runtime_resources()
    assert engine.controller.pid is None
    assert engine.controller.generations.state(endpoint) is GenerationState.RETIRED
    assert lease_store.current(now=datetime.now(timezone.utc)) is None


def test_production_composition_owns_one_worker_for_dual_model_routing(
    canonical_state_path, tmp_path,
):
    digest = installed_core_release_digest()
    primary = ProviderConfiguration(provider="test-llm", model="deep-model")
    secondary = ProviderConfiguration(provider="test-llm", model="fast-model")
    configuration = SofiaConfiguration(
        constitution_path=tmp_path / "constitution.md",
        constitution_hash_path=tmp_path / "constitution.sha256",
        identity_path=tmp_path / "identity.json",
        personality_path=tmp_path / "personality.json",
        avatar_path=tmp_path / "avatar.json",
        state_path=canonical_state_path,
        provider=primary,
        filesystem_root=tmp_path,
        routing=CognitiveRoutingConfiguration(
            enabled=True, primary=primary, secondary=secondary,
        ),
        core_worker=CoreWorkerConfiguration(
            enabled=True, release_digest=digest,
            platform_instance_id="platform:dual-composition-test",
        ),
    )

    runtime = compose(configuration)
    engine = runtime.cognitive_system.engine
    assert isinstance(engine, RoutingCognitiveEngine)
    primary_engine = engine.registry.primary
    secondary_engine = engine.registry.secondary
    assert isinstance(primary_engine, CoreWorkerCognitiveEngine)
    assert isinstance(secondary_engine, CoreWorkerCognitiveEngine)
    assert primary_engine.controller is secondary_engine.controller
    assert primary_engine.controller.pid not in {None, os.getpid()}
    assert primary_engine.configuration == primary
    assert secondary_engine.configuration == secondary

    owner_group = runtime._component_owner
    inference_processes = owner_group.inference_owner.providers
    assert set(inference_processes) == {"primary", "secondary"}
    assert all(
        process.pid not in {None, os.getpid(), primary_engine.controller.pid}
        for process in inference_processes.values()
    )
    assert all(
        process.health().epoch == process.lease.epoch
        for process in inference_processes.values()
    )
    inference_generations = tuple(
        (owner.generations, owner.endpoint)
        for owner in inference_processes.values()
    )
    assert all(
        endpoint is not None and generations.is_active(endpoint)
        for generations, endpoint in inference_generations
    )

    runtime._close_runtime_resources()
    assert primary_engine.controller.pid is None
    assert all(process.pid is None for process in inference_processes.values())
    assert all(
        generations.state(endpoint) is GenerationState.RETIRED
        for generations, endpoint in inference_generations
    )


def test_lifetime_lock_allows_verified_stopped_restart_recovery(canonical_state_path, tmp_path):
    digest = installed_core_release_digest()
    from sofia.platform.core_worker import CoreWorkerProcessOwner

    first = CoreWorkerProcessOwner.start(
        state_path=canonical_state_path, release_digest=digest,
        platform_instance_id="platform:restart-test",
        core_identity_id="core:restart-test", component_id="core.restart-test",
        runtime_dir=tmp_path / "worker", spec=CoreEngineProcessSpec("rule"),
    )
    old = first.controller.endpoint
    process = first.controller._active
    assert old is not None and process is not None and process._process is not None
    process._process.terminate()
    process._process.join(5)
    # Emulate a parent crash: release the expired authority without asking the
    # controller to rewrite generation state. The child-owned lifetime lock is
    # now authoritative evidence that the old process stopped.
    first._stop.set()
    if first._thread is not None:
        first._thread.join(5)
    first.lease_store.release(first.lease, now=datetime.now(timezone.utc))

    recovered = CoreWorkerProcessOwner.start(
        state_path=canonical_state_path, release_digest=digest,
        platform_instance_id="platform:restart-test",
        core_identity_id="core:restart-test", component_id="core.restart-test",
        runtime_dir=tmp_path / "worker", spec=CoreEngineProcessSpec("rule"),
    )
    assert recovered.generations.state(old) is GenerationState.QUARANTINED
    assert recovered.controller.health().ready
    recovered.close()


def test_missing_lifetime_evidence_blocks_automatic_restart(canonical_state_path, tmp_path):
    now = datetime.now(timezone.utc)
    leases = LocalRunLeaseStore(
        canonical_state_path, lease_key="component-core"
    )
    old_lease = leases.acquire(
        owner_id="legacy-platform", now=now, ttl_seconds=180,
    ).lease
    assert old_lease is not None
    generations = ComponentGenerationStore(
        state_path=canonical_state_path, lease_store=leases,
    )
    endpoint = generations.stage(
        component_id="core.legacy-test", kind=ComponentKind.CORE,
        release_digest=sha256(b"legacy").hexdigest(),
        platform_instance_id="platform:legacy", core_identity_id="core:legacy-test",
        lease=old_lease, now=now, reason="legacy generation without lifetime proof",
    )
    generations.activate(endpoint, lease=old_lease, now=now, reason="legacy active")
    leases.release(old_lease, now=now + timedelta(seconds=1))

    from sofia.platform.core_worker import CoreWorkerProcessOwner
    with pytest.raises(CoreWorkerError, match="unknown"):
        CoreWorkerProcessOwner.start(
            state_path=canonical_state_path,
            release_digest=installed_core_release_digest(),
            platform_instance_id="platform:new",
            core_identity_id="core:legacy-test", component_id="core.legacy-test",
            runtime_dir=tmp_path / "missing-proof",
            spec=CoreEngineProcessSpec("rule"),
        )
    assert generations.is_active(endpoint)


def test_application_owner_rejects_forged_release_identity_before_spawn(
    canonical_state_path, tmp_path,
):
    from sofia.platform.core_worker import CoreWorkerProcessOwner

    with pytest.raises(CoreWorkerError, match="does not match installed package"):
        CoreWorkerProcessOwner.start(
            state_path=canonical_state_path, release_digest="0" * 64,
            platform_instance_id="platform:forged-release",
            core_identity_id="core:forged-release",
            component_id="core.forged-release",
            runtime_dir=tmp_path / "forged-release",
            spec=CoreEngineProcessSpec("rule"),
        )


def test_child_independently_rejects_parent_claimed_release_digest(
    canonical_state_path, tmp_path,
):
    now, generations, controller = build(
        canonical_state_path, tmp_path, "core.forged-child"
    )
    forged = "0" * 64
    with pytest.raises(
        CoreWorkerError,
        match="startup rejected: attestation_or_identity_rejected",
    ):
        controller.start(
            release_digest=forged,
            spec=CoreEngineProcessSpec(
                "rule", expected_runtime_digest=forged,
            ),
            now=now,
        )
    rows = generations.active_for_core_identity("core:sofia")
    assert rows is None


def test_installed_release_digest_rejects_symlinked_package_input(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "core.py").write_text("value = 1\n", encoding="utf-8")
    (package / "redirect.py").symlink_to(package / "core.py")

    with pytest.raises(CoreWorkerError, match="symlink"):
        installed_core_release_digest(package)
