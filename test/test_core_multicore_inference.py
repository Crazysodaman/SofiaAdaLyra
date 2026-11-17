"""Per-Core multi-Core inference binding, fairness and recovery regressions."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Thread
from uuid import UUID

import pytest

from sofia.core.multicore.inference import (
    CoreInferenceDenied,
    CoreInferenceConflict,
    CrossCoreContextError,
    InMemoryCoreInferenceJournal,
    MultiCoreInference,
    OperatorStopActive,
    StaleCoreGeneration,
    UnknownCoreBinding,
    UnknownInferenceJob,
    UnsupportedCoreModel,
)
from sofia.platform.inference import (
    BackendOutput, ModelIdentity, ModelResidencyError,
    ModelSubstitutionError, ProviderPolicy, SchedulerLimits, StaticCapacitySource,
    WorkloadClass, ModelResidencyTracker,
)
from sofia.platform.inference.gaming import GamingPolicy
from sofia.platform.ops.activity import ActivityMode
from test._shared_inference_support import (
    MODEL, OTHER_MODEL, AdmissionStub, budgets, capacity, core, footprint,
    user,
)


class EchoBackend:
    def __init__(self, *, fail: bool = False, answer_model=None) -> None:
        self.fail = fail
        self.answer_model = answer_model
        self.calls = []
        self.cancelled = []

    def generate(self, call):
        self.calls.append(call)
        if self.fail:
            raise RuntimeError("simulated provider failure")
        model = self.answer_model or call.model
        return BackendOutput(
            model=model,
            text=f"echo:{call.messages[-1].content}",
            prompt_tokens=10,
            generated_tokens=2,
            time_to_first_token_ms=1.0,
            total_duration_ms=4.0,
            simulated=True,
        )

    def cancel(self, job_id: str) -> bool:
        self.cancelled.append(job_id)
        return True


@dataclass
class SafetyGate:
    stopped: bool = False
    allowed: bool = True

    def is_operator_stopped(self) -> bool:
        return self.stopped

    def permits_inference(self, *, core_id: UUID, conversation_id: str) -> bool:
        return self.allowed


def build_service(
    *, models=(MODEL,), backend=None, policy=None, installed=None,
    max_parallel: int = 1, journal=None, safety=None,
    limits: SchedulerLimits | None = None,
) -> MultiCoreInference:
    configured = tuple(models)
    return MultiCoreInference(
        backend=backend if backend is not None else EchoBackend(),
        admission=AdmissionStub(),
        models={model: footprint() for model in configured},
        policy=policy if policy is not None else ProviderPolicy.local_only(
            configured
        ),
        residency=ModelResidencyTracker(
            installed if installed is not None else configured,
            max_loaded_models=len(configured),
        ),
        capacity=StaticCapacitySource(capacity(activity=ActivityMode.IDLE)),
        budgets=budgets(),
        scheduler_limits=limits,
        gaming=GamingPolicy(allow_background_preload=True),
        clock=lambda: 1_000.0,
        max_parallel=max_parallel,
        journal=journal,
        safety=safety,
    )


def _bind(service, owner, *, conversation_id="conv:one"):
    service.register_core(
        core_id=owner.core_id,
        platform_id=owner.platform_id,
        generation=owner.generation,
        display_name=owner.display_name,
        model=MODEL,
    )
    return service.open_conversation(
        core_id=owner.core_id,
        platform_id=owner.platform_id,
        generation=owner.generation,
        conversation_id=conversation_id,
    )


def test_exact_bindings_keep_independent_contexts_and_prompts() -> None:
    backend = EchoBackend()
    service = build_service(backend=backend)
    first, second = core(1), core(2)
    first_binding = _bind(service, first, conversation_id="conv:shared")
    second_binding = _bind(service, second, conversation_id="conv:shared")

    service.append_context(first_binding, (user("only-alpha"),))
    service.append_context(second_binding, (user("only-beta"),))

    assert [
        item.content
        for item in service.assemble_prompt(first_binding)
    ] == ["only-alpha"]
    assert [
        item.content
        for item in service.assemble_prompt(second_binding)
    ] == ["only-beta"]

    first_submit = service.submit(
        first_binding, request_id="req:alpha", max_output_tokens=8,
        workload_class=WorkloadClass.CORE_SOCIAL,
    )
    second_submit = service.submit(
        second_binding, request_id="req:beta", max_output_tokens=8,
        workload_class=WorkloadClass.CORE_SOCIAL,
    )
    assert first_submit.accepted and second_submit.accepted

    alpha = service.dispatch_next()
    beta = service.dispatch_next()
    assert alpha.result is not None and beta.result is not None
    assert alpha.result.core_id == first.core_id
    assert beta.result.core_id == second.core_id
    assert alpha.result.text == "echo:only-alpha"
    assert beta.result.text == "echo:only-beta"
    assert alpha.result.conversation_id == "conv:shared"
    assert beta.result.conversation_id == "conv:shared"
    assert backend.calls[0].messages[-1].content == "only-alpha"
    assert backend.calls[1].messages[-1].content == "only-beta"


def test_model_selection_is_per_core_on_one_shared_backend() -> None:
    backend = EchoBackend()
    service = build_service(models=(MODEL, OTHER_MODEL), backend=backend)
    first, second = core(11), core(12)
    service.register_core(
        core_id=first.core_id, platform_id=first.platform_id,
        generation=1, display_name=first.display_name, model=MODEL,
    )
    service.register_core(
        core_id=second.core_id, platform_id=second.platform_id,
        generation=1, display_name=second.display_name, model=OTHER_MODEL,
    )
    first_binding = service.open_conversation(
        core_id=first.core_id, platform_id=first.platform_id,
        generation=1, conversation_id="conv:model-one",
    )
    second_binding = service.open_conversation(
        core_id=second.core_id, platform_id=second.platform_id,
        generation=1, conversation_id="conv:model-two",
    )
    for binding, text in ((first_binding, "alpha"), (second_binding, "beta")):
        assert service.submit(
            binding, request_id=f"req:{text}", messages=(user(text),),
            max_output_tokens=8,
        ).accepted

    outcomes = [service.dispatch_next(), service.dispatch_next()]
    results = {outcome.result.core_id: outcome.result for outcome in outcomes}
    assert results[first.core_id].model == MODEL
    assert results[second.core_id].model == OTHER_MODEL
    assert results[first.core_id].model.provider == "ollama"
    assert len(backend.calls) == 2
    assert all(call.request.core.platform_id == "platform:test" for call in backend.calls)


def test_cancel_is_owner_bound_and_queued_timeouts_expire_truthfully() -> None:
    backend = EchoBackend()
    service = build_service(backend=backend)
    first, second = core(21), core(22)
    first_binding = _bind(service, first, conversation_id="conv:cancel")
    second_binding = _bind(service, second, conversation_id="conv:cancel")
    first_submit = service.submit(
        first_binding, request_id="req:cancel", messages=(user("cancel"),),
        max_output_tokens=8,
    )
    second_submit = service.submit(
        second_binding, request_id="req:other", messages=(user("expire"),),
        max_output_tokens=8,
    )
    assert first_submit.job_id and second_submit.job_id

    with pytest.raises(CrossCoreContextError):
        service.cancel(second_binding, first_submit.job_id)

    cancelled = service.cancel(first_binding, first_submit.job_id)
    assert cancelled.outcome.value == "cancelled"
    assert any(
        failure.request_id == "req:cancel"
        for failure in service.failures(first_binding)
    )

    expired = service.timeouts(now=1_000.0 + 121.0)
    assert second_submit.job_id in expired
    assert service.dispatch_next().result is None


def test_cancel_unknown_job_is_explicit_and_backend_failure_is_truthful() -> None:
    backend = EchoBackend(fail=True)
    service = build_service(backend=backend)
    owner = core(31)
    binding = _bind(service, owner)
    with pytest.raises(UnknownInferenceJob):
        service.cancel(binding, "missing-job")

    assert service.submit(
        binding, request_id="req:fail", messages=(user("fail"),),
        max_output_tokens=8,
    ).accepted
    with pytest.raises(ModelResidencyError):
        service.dispatch_next()
    assert service.results(binding) == ()
    assert service.failures(binding)
    assert service.pending()
    recovered = service.recover_after_restart(now=1_001.0)
    assert recovered
    assert "restarted" in recovered[0].reason


def test_restart_continuity_keeps_results_and_rejects_stale_generation() -> None:
    journal = InMemoryCoreInferenceJournal()
    backend = EchoBackend()
    service = build_service(backend=backend, journal=journal)
    owner = core(41)
    binding = _bind(service, owner, conversation_id="conv:restart")
    service.append_context(binding, (user("remember this"),))
    assert service.submit(
        binding, request_id="req:restart", max_output_tokens=8,
    ).accepted
    first = service.dispatch_next()
    assert first.result is not None

    restarted = build_service(backend=EchoBackend(), journal=journal)
    recovered_binding = restarted.open_conversation(
        core_id=owner.core_id, platform_id=owner.platform_id,
        generation=owner.generation, conversation_id="conv:restart",
    )
    assert [
        item.content for item in restarted.assemble_prompt(recovered_binding)
    ] == ["remember this"]
    outcomes = restarted.results(recovered_binding)
    assert outcomes and outcomes[0].result.output_sha256 == first.result.output_sha256

    newer = core(41, generation=2)
    restarted.register_core(
        core_id=newer.core_id, platform_id=newer.platform_id,
        generation=2, display_name=newer.display_name, model=MODEL,
    )
    with pytest.raises(StaleCoreGeneration):
        restarted.open_conversation(
            core_id=owner.core_id, platform_id=owner.platform_id,
            generation=1, conversation_id="conv:new",
        )
    newer_binding = restarted.open_conversation(
        core_id=newer.core_id, platform_id=newer.platform_id,
        generation=2, conversation_id="conv:restart",
    )
    assert restarted.assemble_prompt(newer_binding) == ()


def test_bounded_global_concurrency_reports_saturation() -> None:
    started = Event()
    release = Event()

    class BlockingBackend(EchoBackend):
        def generate(self, call):
            self.calls.append(call)
            started.set()
            release.wait(timeout=5.0)
            return BackendOutput(
                model=call.model,
                text="echo:held",
                prompt_tokens=4,
                generated_tokens=2,
                time_to_first_token_ms=1.0,
                total_duration_ms=4.0,
                simulated=True,
            )

    backend = BlockingBackend()
    service = build_service(backend=backend, max_parallel=1)
    owner = core(51)
    binding = _bind(service, owner)
    assert service.submit(
        binding, request_id="req:block", messages=(user("hold"),),
        max_output_tokens=8,
    ).accepted
    worker = Thread(target=service.dispatch_next)
    worker.start()
    assert started.wait(timeout=5.0)
    saturated = service.dispatch_next()
    assert saturated.result is None
    assert "bounded concurrency" in (saturated.reason or "")
    release.set()
    worker.join(timeout=5.0)
    assert not worker.is_alive()


def test_no_cloud_fallback_or_model_substitution() -> None:
    with pytest.raises(CoreInferenceDenied):
        build_service(policy=ProviderPolicy(
            (MODEL,), allow_cloud_fallback=True,
        ))

    backend = EchoBackend(answer_model=OTHER_MODEL)
    service = build_service(backend=backend)
    owner = core(61)
    binding = _bind(service, owner)
    assert service.submit(
        binding, request_id="req:substitute", messages=(user("substitute"),),
        max_output_tokens=8,
    ).accepted
    with pytest.raises(ModelSubstitutionError):
        service.dispatch_next()
    assert service.results(binding) == ()
    assert service.failures(binding)

    unknown = core(62)
    service.register_core(
        core_id=unknown.core_id, platform_id=unknown.platform_id,
        generation=1, display_name=unknown.display_name, model=MODEL,
    )
    with pytest.raises(UnsupportedCoreModel):
        service.register_core(
            core_id=unknown.core_id, platform_id=unknown.platform_id,
            generation=1, display_name=unknown.display_name,
            model=ModelIdentity("cloud", "remote:70b", "c" * 64),
        )


def test_safe_and_operator_stop_boundaries_deny_inference() -> None:
    gate = SafetyGate(stopped=True)
    service = build_service(safety=gate)
    owner = core(71)
    service.register_core(
        core_id=owner.core_id, platform_id=owner.platform_id,
        generation=1, display_name=owner.display_name, model=MODEL,
    )
    binding = service.open_conversation(
        core_id=owner.core_id, platform_id=owner.platform_id,
        generation=1, conversation_id="conv:safe",
    )
    with pytest.raises(OperatorStopActive):
        service.submit(binding, request_id="req:stop", max_output_tokens=8)

    gate.stopped = False
    gate.allowed = False
    with pytest.raises(CoreInferenceDenied):
        service.submit(binding, request_id="req:denied", max_output_tokens=8)

    gate.allowed = True
    assert service.submit(
        binding, request_id="req:allowed", messages=(user("allowed"),),
        max_output_tokens=8,
    ).accepted
    gate.stopped = True
    with pytest.raises(OperatorStopActive):
        service.dispatch_next()


def test_text_only_and_conflicting_bindings() -> None:
    service = build_service()
    owner = core(81)
    binding = _bind(service, owner)
    with pytest.raises(TypeError):
        service.append_context(binding, (object(),))
    with pytest.raises(ValueError):
        service.submit(binding, request_id="req:empty", max_output_tokens=8)
    assert service.submit(
        binding, request_id="req:same", messages=(user("one"),),
        max_output_tokens=8,
    ).accepted
    with pytest.raises(CoreInferenceConflict):
        service.submit(
            binding, request_id="req:same", messages=(user("two"),),
            max_output_tokens=8,
        )

    unregistered = core(82)
    with pytest.raises(UnknownCoreBinding):
        service.open_conversation(
            core_id=unregistered.core_id,
            platform_id=unregistered.platform_id,
            generation=1,
            conversation_id="conv:missing",
        )
