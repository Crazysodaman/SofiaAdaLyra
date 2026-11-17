"""Shared-model benchmark profile regressions; simulated evidence only."""
from datetime import datetime, timezone

import pytest

from sofia.platform.inference import (
    BenchmarkMeasurement, BenchmarkProfile, CapacityDenied, EvidenceLevel,
    RealBenchmarkApproval, SHARED_CONTEXT_TOKENS, SHARED_MODEL_FAMILY,
    SharedModelBenchmarkHarness,
)
from test._shared_inference_support import MODEL, capacity, footprint


def measurement(parallelism: int = 1, evidence: EvidenceLevel = EvidenceLevel.SIMULATED):
    return BenchmarkMeasurement(
        parallelism=parallelism,
        time_to_first_token_ms=250.0,
        tokens_per_second=45.0,
        total_latency_ms=2_000.0,
        footprint=footprint(),
        peak_vram_bytes=9_000,
        host_ram_bytes=20_000,
        gpu_utilization_percent=80.0,
        game_impact_ms=4.0,
        evidence_level=evidence,
    )


def real_capacity():
    return capacity(
        vram_total=16_000, vram_free=12_000, simulated=False, measured=True,
    )


def test_simulated_profile_records_required_measurements_and_one_model() -> None:
    profile = BenchmarkProfile(MODEL)
    harness = SharedModelBenchmarkHarness(
        profile, capacity(vram_total=16_000, vram_free=12_000),
    )
    report = harness.simulate((measurement(),), now=1_000.0)

    assert profile.context_tokens == SHARED_CONTEXT_TOKENS == 4096
    assert SHARED_MODEL_FAMILY in profile.model.model
    assert report.evidence_level is EvidenceLevel.SIMULATED
    assert report.approved_real_host is False
    assert report.loaded_models == 1
    assert report.load_count == 1
    sample = report.measurement_for(1)
    assert sample is not None
    assert sample.time_to_first_token_ms == 250.0
    assert sample.tokens_per_second == 45.0
    assert sample.total_latency_ms == 2_000.0
    assert sample.footprint.weights_bytes > 0
    assert sample.footprint.kv_cache_bytes > 0
    assert sample.footprint.runtime_bytes > 0
    assert sample.footprint.safety_headroom_bytes > 0
    assert sample.peak_vram_bytes == 9_000
    assert sample.host_ram_bytes == 20_000
    assert sample.gpu_utilization_percent == 80.0
    assert sample.game_impact_ms == 4.0


def test_two_way_parallelism_requires_measured_capacity_headroom() -> None:
    tight = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), capacity(vram_total=16_000, vram_free=7_500),
    )
    with pytest.raises(CapacityDenied, match="parallelism"):
        tight.simulate((measurement(parallelism=2),), now=1_000.0)

    enough = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), capacity(vram_total=16_000, vram_free=9_000),
    )
    report = enough.simulate((measurement(parallelism=2),), now=1_000.0)
    assert report.measurement_for(2) is not None


def test_unmeasured_or_stale_benchmark_capacity_is_refused() -> None:
    unmeasured = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), capacity(measured=False),
    )
    with pytest.raises(CapacityDenied, match="not measured"):
        unmeasured.simulate((measurement(),), now=1_000.0)

    stale = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), capacity(now=1_000.0, ttl=10.0),
    )
    with pytest.raises(CapacityDenied, match="stale"):
        stale.simulate((measurement(),), now=1_020.0)


def test_simulated_harness_refuses_to_label_observed_evidence() -> None:
    harness = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), capacity(vram_total=16_000, vram_free=12_000),
    )
    with pytest.raises(ValueError, match="simulated evidence"):
        harness.simulate(
            (measurement(evidence=EvidenceLevel.OBSERVED),), now=1_000.0,
        )


def test_real_benchmark_requires_explicit_approval_and_observed_runner() -> None:
    harness = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL), real_capacity(),
    )
    with pytest.raises(PermissionError, match="approval"):
        harness.run_real(
            approval=None, runner=lambda profile: (), now=1_000.0,
        )

    approval = RealBenchmarkApproval(
        "host:test", "owner:test", "approval:benchmark-1",
        datetime.now(timezone.utc),
    )
    wrong_host = RealBenchmarkApproval(
        "host:other", "owner:test", "approval:benchmark-2",
        datetime.now(timezone.utc),
    )
    with pytest.raises(PermissionError, match="different host"):
        harness.run_real(
            approval=wrong_host, runner=lambda profile: (), now=1_000.0,
        )

    report = harness.run_real(
        approval=approval,
        runner=lambda profile: (measurement(evidence=EvidenceLevel.OBSERVED),),
        now=1_000.0,
    )
    assert report.evidence_level is EvidenceLevel.OBSERVED
    assert report.approved_real_host is True

    with pytest.raises(RuntimeError, match="observed"):
        harness.run_real(
            approval=approval,
            runner=lambda profile: (measurement(evidence=EvidenceLevel.SIMULATED),),
            now=1_000.0,
        )


def test_real_benchmark_refuses_simulated_host_capacity() -> None:
    harness = SharedModelBenchmarkHarness(
        BenchmarkProfile(MODEL),
        capacity(vram_total=16_000, vram_free=12_000, simulated=True),
    )
    approval = RealBenchmarkApproval(
        "host:test", "owner:test", "approval:benchmark-1",
        datetime.now(timezone.utc),
    )
    with pytest.raises(PermissionError, match="measured"):
        harness.run_real(
            approval=approval,
            runner=lambda profile: (measurement(evidence=EvidenceLevel.OBSERVED),),
            now=1_000.0,
        )


def test_profile_never_allows_more_than_one_loaded_model() -> None:
    with pytest.raises(ValueError, match="one loaded model"):
        BenchmarkProfile(MODEL, max_loaded_models=2)

def test_profile_starts_with_one_active_generation() -> None:
    profile = BenchmarkProfile(MODEL)
    assert profile.parallelism_candidates[0] == 1
