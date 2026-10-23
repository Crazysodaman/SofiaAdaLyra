"""Deferred Phase 11 source-only model benchmark evidence integrity tests."""
from dataclasses import replace

import pytest

from sofia.core.cognition.model_admission import (
    ModelTrialEvidence, compare_models,
)


pytestmark = pytest.mark.pkg_core


def reviewed(model="owner/candidate"):
    return ModelTrialEvidence(
        model=model,
        evaluation_set_sha256="a" * 64,
        code_revision="reviewed-revision",
        independent_reviewer="human-reviewed-evaluation",
        evaluated_cases=40,
        correct_cases=36,
        safety_violations=0,
        false_action_claims=0,
        p95_latency_ms=650.0,
        peak_ram_mb=1200.0,
        peak_vram_mb=0.0,
    )


@pytest.mark.parametrize(
    "metric", ["p95_latency_ms", "peak_ram_mb"],
)
def test_zero_measured_latency_or_ram_cannot_fake_benchmark_improvement(metric):
    with pytest.raises(ValueError, match="must be positive"):
        replace(reviewed(), **{metric: 0.0})


def test_zero_gpu_vram_can_be_legitimate_cpu_only_observation():
    trial=reviewed()
    assert trial.peak_vram_mb == 0
    comparison=compare_models(
        reviewed("owner/baseline"),
        replace(trial, correct_cases=38),
        max_p95_ms=1000,
        max_ram_mb=2000,
        max_vram_mb=1024,
    )
    assert comparison.eligible_for_operator_review is True
    assert comparison.permission_to_switch is False
