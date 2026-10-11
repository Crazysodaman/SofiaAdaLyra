"""Deferred WS4 Phase 11 Fleet GPU-admission regressions.

The RTX 3060 / 32 GiB configuration is a *synthetic capacity fixture* here,
not discovered or enrolled hardware. These tests do not run inference.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from sofia.ops.model import FleetHost, HostLifecycle, HostTelemetry, WorkloadContract
from sofia.ops.placement import PlacementEngine


NOW = datetime(2026, 10, 11, 20, tzinfo=timezone.utc)
GIB = 1024 ** 3


def worker(*, trusted=True, telemetry=None, lifecycle=HostLifecycle.HEALTHY):
    return FleetHost(
        host_id="candidate-unknown-name",
        platform="windows", architecture="x86_64",
        lifecycle=lifecycle, trusted=trusted, telemetry=telemetry,
    )


def capacity(*, at=NOW, ram_total=32*GIB, ram_used=4*GIB,
             vram_total=8*GIB, vram_used=1*GIB, gpu_percent=10.0):
    return HostTelemetry(
        at, cpu_percent=12.0,
        ram_total_bytes=ram_total, ram_used_bytes=ram_used,
        gpu_percent=gpu_percent,
        vram_total_bytes=vram_total, vram_used_bytes=vram_used,
        storage_free_bytes=80 * GIB,
    )


def inference_contract():
    # A reviewed inference image's exact memory requirement must be set by
    # independent measurements, NEVER inferred from a card's advertised VRAM.
    return WorkloadContract(
        workload_id="synthetic-fast-model", version="1",
        supported_platforms=("windows","linux"),
        supported_architectures=("x86_64",),
        min_ram_bytes=4*GIB,
        gpu_required=True,
        min_vram_bytes=5*GIB,
    )


def decide(host,*,now=NOW):
    return PlacementEngine().choose(
        inference_contract(),(host,),now=now,
    )


def test_owner_reported_ram_and_gpu_are_not_an_enrollment_credential():
    observed=worker(trusted=False,telemetry=capacity())
    result=decide(observed)
    assert result.host_id is None
    assert "not trusted" in result.rejected[0][1]
    unapproved=worker(
        lifecycle=HostLifecycle.CANDIDATE,
        telemetry=capacity(),
    )
    assert decide(unapproved).host_id is None


def test_unknown_memory_is_not_pretended_available_for_gpu_inference():
    for telemetry in (
        capacity(ram_total=None,ram_used=None),
        capacity(vram_total=None,vram_used=None),
        capacity(gpu_percent=None),
    ):
        result=decide(worker(telemetry=telemetry))
        assert result.host_id is None


def test_stale_or_future_host_gpu_metrics_cannot_select_a_worker():
    for at in (
        NOW-timedelta(minutes=3),
        NOW+timedelta(minutes=2),
    ):
        result=decide(worker(telemetry=capacity(at=at)))
        assert result.host_id is None
        assert "telemetry expired" in result.rejected[0][1]


def test_verified_synthetic_eight_gib_gpu_with_sufficient_headroom_can_rank():
    selected=decide(worker(telemetry=capacity()))
    assert selected.host_id=="candidate-unknown-name"
    assert selected.rejected==()


def test_vram_capacity_is_free_headroom_not_advertised_card_capacity():
    selected=decide(
        worker(telemetry=capacity(vram_total=8*GIB,vram_used=4*GIB))
    )
    assert selected.host_id is None
    assert "VRAM headroom" in selected.rejected[0][1]


def test_naive_placement_clock_fails_closed():
    with pytest.raises(ValueError,match="timezone-aware"):
        decide(worker(telemetry=capacity()),now=NOW.replace(tzinfo=None))
