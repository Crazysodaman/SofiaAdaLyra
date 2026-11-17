"""Capacity, gaming, preload and model-residency regressions."""
import pytest

from sofia.platform.inference import (
    CapacityDenied, GamingPolicy, ModelFootprint, ModelResidencyError,
    ModelResidencyTracker, StaticCapacitySource, WorkloadClass,
    effective_parallelism,
)
from sofia.platform.ops.activity import ActivityMode
from test._shared_inference_support import (
    MODEL, OTHER_MODEL, FakeBackend, build_adapter, capacity, core, footprint,
    user,
)


def test_stale_capacity_denies_dispatch_without_backend_call() -> None:
    backend = FakeBackend()
    source = StaticCapacitySource(capacity(now=1_000.0, ttl=10.0))
    adapter = build_adapter(backend=backend, source=source)
    adapter.submit(
        request_id="stale", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=10,
    )
    outcome = adapter.dispatch_next(now=1_020.0)
    assert outcome.result is None
    assert "stale" in (outcome.reason or "")
    assert adapter.scheduler.status("stale").state.value == "queued"
    assert backend.calls == []
    assert adapter.telemetry().capacity_denials == 1


def test_unmeasured_capacity_denies_dispatch() -> None:
    adapter = build_adapter(source=StaticCapacitySource(capacity(measured=False)))
    adapter.submit(
        request_id="unknown", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=10,
    )
    outcome = adapter.dispatch_next(now=1_000.0)
    assert outcome.result is None
    assert "not measured" in (outcome.reason or "")


def test_parallelism_is_limited_to_one_unless_measured_capacity_allows_two() -> None:
    one = build_adapter(
        max_parallel=2,
        source=StaticCapacitySource(
            capacity(vram_total=16_000, vram_free=7_500),
        ),
    )
    assert one.capacity_decision(now=1_000.0).parallel_slots == 1

    two = build_adapter(
        max_parallel=2,
        source=StaticCapacitySource(
            capacity(vram_total=16_000, vram_free=9_000),
        ),
    )
    assert two.capacity_decision(now=1_000.0).parallel_slots == 2

    snapshot = capacity(vram_total=16_000, vram_free=9_000)
    assert effective_parallelism(
        snapshot, footprint(), active_generations=0, requested_max=2,
        now=1_000.0, already_resident=False,
    ) == 2
    assert effective_parallelism(
        capacity(vram_free=7_500), footprint(), active_generations=0,
        requested_max=2, now=1_000.0, already_resident=False,
    ) == 1


def test_gaming_admits_resident_foreground_and_defers_social() -> None:
    backend = FakeBackend()
    idle = StaticCapacitySource(capacity(activity=ActivityMode.IDLE))
    adapter = build_adapter(backend=backend, source=idle)
    adapter.residency.ensure_loaded(
        MODEL, footprint(), capacity(activity=ActivityMode.IDLE), 1_000.0,
    )
    idle.replace(capacity(activity=ActivityMode.GAMING))

    for request_id, workload in (
        ("owner", WorkloadClass.FOREGROUND_OWNER),
        ("social", WorkloadClass.CORE_SOCIAL),
    ):
        adapter.submit(
            request_id=request_id, core=core(1), conversation_id=f"conv:{request_id}",
            workload_class=workload, messages=(user("hello"),),
            max_output_tokens=10,
        )

    first = adapter.dispatch_next(now=1_000.0)
    assert first.result is not None
    assert first.result.request_id == "owner"
    assert backend.calls and backend.calls[0].job_id == "owner"

    second = adapter.dispatch_next(now=1_000.0)
    assert second.result is None
    assert adapter.scheduler.status("social").state.value == "deferred"

    idle.replace(capacity(activity=ActivityMode.NORMAL))
    third = adapter.dispatch_next(now=1_000.0)
    assert third.result is not None
    assert third.result.request_id == "social"


def test_background_preload_is_disabled_even_when_idle() -> None:
    adapter = build_adapter(
        source=StaticCapacitySource(capacity(activity=ActivityMode.IDLE)),
    )
    decision = adapter.preload(now=1_000.0)
    assert decision.allowed is False
    assert "preload" in (decision.reason or "")
    assert adapter.telemetry().residency.load_count == 0


def test_background_preload_is_not_allowed_while_gaming() -> None:
    adapter = build_adapter(
        source=StaticCapacitySource(capacity(activity=ActivityMode.GAMING)),
        gaming=GamingPolicy(allow_background_preload=True),
    )
    decision = adapter.preload(now=1_000.0)
    assert decision.allowed is False


def test_cold_social_inference_is_deferred_instead_of_preloading() -> None:
    backend = FakeBackend()
    adapter = build_adapter(
        backend=backend,
        source=StaticCapacitySource(capacity(activity=ActivityMode.NORMAL)),
    )
    adapter.submit(
        request_id="social", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.CORE_SOCIAL,
        messages=(user("hello"),), max_output_tokens=10,
    )
    outcome = adapter.dispatch_next(now=1_000.0)
    assert outcome.result is None
    assert adapter.scheduler.status("social").state.value == "deferred"
    assert backend.calls == []
    assert adapter.telemetry().residency.load_count == 0


def test_explicitly_allowed_background_work_resumes_when_idle() -> None:
    backend = FakeBackend()
    source = StaticCapacitySource(capacity(activity=ActivityMode.NORMAL))
    adapter = build_adapter(
        backend=backend, source=source,
        gaming=GamingPolicy(allow_background_preload=True),
    )
    adapter.submit(
        request_id="social", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.CORE_SOCIAL,
        messages=(user("hello"),), max_output_tokens=10,
    )
    assert adapter.dispatch_next(now=1_000.0).result is None
    source.replace(capacity(activity=ActivityMode.IDLE))
    outcome = adapter.dispatch_next(now=1_000.0)
    assert outcome.result is not None
    assert outcome.result.request_id == "social"


def test_cpu_fallback_is_unauthorized_by_default() -> None:
    policy = GamingPolicy()
    assert policy.cpu_fallback_allowed(ActivityMode.NORMAL) is False
    assert policy.cpu_fallback_allowed(ActivityMode.GAMING) is False
    adapter = build_adapter(installed=())
    decision = adapter.submit(
        request_id="cold", core=core(1), conversation_id="conv",
        workload_class=WorkloadClass.FOREGROUND_OWNER,
        messages=(user("hello"),), max_output_tokens=10,
    )
    assert decision.accepted is False
    assert "CPU fallback" in (decision.reason or "")


def test_one_exact_model_is_loaded_once_and_idle_reclaimed_after_keep_alive() -> None:
    backend = FakeBackend()
    adapter = build_adapter(
        backend=backend, keep_alive_seconds=10.0,
        source=StaticCapacitySource(capacity(activity=ActivityMode.IDLE)),
    )
    for index in range(2):
        adapter.submit(
            request_id=f"req{index}", core=core(1),
            conversation_id=f"conv{index}",
            workload_class=WorkloadClass.FOREGROUND_OWNER,
            messages=(user("hello"),), max_output_tokens=10,
        )
        assert adapter.dispatch_next(now=1_000.0).result is not None
    telemetry = adapter.telemetry()
    assert telemetry.residency.load_count == 1
    assert telemetry.residency.loaded == (MODEL,)
    assert len(backend.calls) == 2

    assert adapter.reclaim(now=1_020.0) == (MODEL,)
    assert adapter.telemetry().residency.loaded == ()
    assert adapter.telemetry().residency.unload_count == 1


def test_active_generation_prevents_model_unload() -> None:
    tracker = ModelResidencyTracker((MODEL,))
    tracker.ensure_loaded(MODEL, footprint(), capacity(), 1_000.0)
    tracker.begin_generation(MODEL, 1_000.0)
    with pytest.raises(ModelResidencyError, match="active"):
        tracker.unload(MODEL, 1_001.0)
    tracker.end_generation(MODEL, 1_002.0)
    assert tracker.unload(MODEL, 1_003.0) is True


def test_second_model_cannot_hot_swap_the_loaded_model() -> None:
    tracker = ModelResidencyTracker((MODEL, OTHER_MODEL), max_loaded_models=1)
    tracker.ensure_loaded(MODEL, footprint(), capacity(), 1_000.0)
    with pytest.raises(ModelResidencyError, match="limit"):
        tracker.ensure_loaded(
            OTHER_MODEL,
            ModelFootprint(2_000, 500, 200, 300, True, True),
            capacity(), 1_000.0,
        )
    assert tracker.loaded == (MODEL,)


def test_model_residency_is_denied_without_enough_free_vram() -> None:
    tracker = ModelResidencyTracker((MODEL,))
    with pytest.raises(CapacityDenied, match="VRAM"):
        tracker.ensure_loaded(
            MODEL, footprint(), capacity(vram_total=8_000, vram_free=5_000),
            1_000.0,
        )
    assert tracker.loaded == ()


def test_footprint_evidence_is_not_promoted_to_real() -> None:
    simulated = footprint()
    assert simulated.evidence_level == "simulated"
    measured = footprint(simulated=False, measured=True)
    assert measured.evidence_level == "measured"

def test_core_to_core_inference_yields_during_gaming() -> None:
    policy = GamingPolicy()
    assert policy.core_to_core_yields_to(ActivityMode.GAMING) is True
    decision = policy.decision(WorkloadClass.CORE_SOCIAL, ActivityMode.GAMING)
    assert decision.allowed is False
    assert decision.deferred is True
