from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os

import pytest

from sofia.core.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveRole, CognitiveToolDefinition,
)
from sofia.platform.core_worker import (
    CoreEngineProcessSpec, CoreWorkerController, CoreWorkerCognitiveEngine,
    CoreWorkerError,
    CoreWorkerRuntimeBackend,
)
from sofia.platform.composition.engines import create_cognitive_engine
from sofia.platform.composition.root import compose
from sofia.platform.config.model import (
    CoreWorkerConfiguration, ProviderConfiguration, SofiaConfiguration,
)
from sofia.platform.run import ComponentGenerationStore, GenerationState, LocalRunLeaseStore
from sofia.platform.run import ComponentRuntimeSupervisor, ComponentSpec
from sofia.platform.run.components import ComponentKind as SupervisedComponentKind
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


def test_codec_preserves_identity_memory_and_tool_proposals_exactly():
    original = request()
    assert decode_request(encode_request(original)) == original


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


def test_production_composition_owns_configured_core_process(canonical_state_path, tmp_path):
    digest = sha256(b"installed-core-release").hexdigest()
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


def test_lifetime_lock_allows_verified_stopped_restart_recovery(canonical_state_path, tmp_path):
    digest = sha256(b"restart-safe-core").hexdigest()
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
            release_digest=sha256(b"new").hexdigest(),
            platform_instance_id="platform:new",
            core_identity_id="core:legacy-test", component_id="core.legacy-test",
            runtime_dir=tmp_path / "missing-proof",
            spec=CoreEngineProcessSpec("rule"),
        )
    assert generations.is_active(endpoint)
