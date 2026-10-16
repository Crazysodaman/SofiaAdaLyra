"""Host resource instrument tests: no fabricated GPU/quality/soak receipts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.verify import v18_live_resource_probe as probe

pytestmark = pytest.mark.pkg_verify
SHA = "a" * 40
NOW = datetime(2026, 10, 15, 20, tzinfo=timezone.utc)


def sensors(cpu=None, ram=None, total=None, gpu=None, vram=None,
            vram_total=None, power=None):
    return dict(zip(probe._METRICS, (cpu, ram, total, gpu, vram,
                                   vram_total, power), strict=True))


def test_empty_optional_sensors_are_unknown_not_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_revision", lambda _: SHA)
    report = probe.observe_host(
        repo=tmp_path, expected_revision=SHA, declared_role="venus",
        scenario="gaming", count=3, interval_seconds=0,
        collector=lambda: sensors(cpu=35.0, ram=100, total=500),
        pause=lambda _: None, clock=lambda: NOW,
    )
    assert report["sample_count"] == 3
    assert report["summary"]["gpu_vram_used_mib"]["p95"] is None
    assert report["summary"]["gpu_vram_used_mib"]["observed_samples"] == 0
    assert report["summary"]["system_ram_used_bytes"]["p50"] == 100
    assert report["scenario_independently_verified"] is False
    assert report["device_identity_independently_verified"] is False
    assert report["gate4_acceptance"] is False
    assert report["sofia_process_resource_attribution"] is False
    assert "hostname" not in str(report)
    assert "command_line" not in str(report)


def test_nearest_rank_percentiles_use_measured_values_only(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_revision", lambda _: SHA)
    values = iter((sensors(cpu=x) for x in (5, 10, 20, 30, 80)))
    report = probe.observe_host(
        repo=tmp_path, expected_revision=SHA, declared_role="other",
        scenario="idle", count=5, interval_seconds=0,
        collector=lambda: next(values), pause=lambda _: None, clock=lambda: NOW,
    )
    cpu = report["summary"]["system_cpu_percent"]
    assert cpu["min"] == 5
    assert cpu["p50"] == 20
    assert cpu["p95"] == 80
    assert cpu["max"] == 80


def test_revision_mismatch_prevents_collecting_and_changed_head_rejects(tmp_path, monkeypatch):
    attempted = []
    monkeypatch.setattr(probe, "_revision", lambda _: "b" * 40)
    with pytest.raises(probe.HostObservationError, match="revision"):
        probe.observe_host(
            repo=tmp_path, expected_revision=SHA, declared_role="venus",
            scenario="idle", count=1, interval_seconds=0,
            collector=lambda: attempted.append(1) or sensors(),
        )
    assert attempted == []
    values = iter((SHA, "b" * 40))
    monkeypatch.setattr(probe, "_revision", lambda _: next(values))
    with pytest.raises(probe.HostObservationError, match="changed"):
        probe.observe_host(
            repo=tmp_path, expected_revision=SHA, declared_role="venus",
            scenario="idle", count=1, interval_seconds=0,
            collector=lambda: sensors(),
        )


@pytest.mark.parametrize("bad", [
    sensors(cpu=101),
    sensors(ram=800, total=400),
    sensors(vram=400, vram_total=100),
    sensors(gpu=float("nan")),
    sensors(power=-1),
    sensors(cpu=True),
    {"system_cpu_percent": 12},
])
def test_malformed_sensor_data_fail_closed(bad):
    with pytest.raises(probe.HostObservationError):
        probe._validated(bad)


def test_fixed_gpu_query_never_requires_a_real_gpu(monkeypatch):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("nvidia-smi not installed")
    monkeypatch.setattr(probe.subprocess, "run", unavailable)
    assert all(value is None for value in probe._gpu_metrics().values())


def test_operator_labels_cannot_claim_independent_windows_or_sofia_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "_revision", lambda _: SHA)
    monkeypatch.setattr(probe.platform, "system", lambda: "Linux")
    report = probe.observe_host(
        repo=tmp_path, expected_revision=SHA, declared_role="venus",
        scenario="conversation", count=1, interval_seconds=0,
        collector=lambda: sensors(cpu=0), clock=lambda: NOW,
    )
    assert report["actual_platform"] == "linux"
    assert report["declared_host_role"] == "venus"
    assert not report["device_identity_independently_verified"]
    assert not report["application_quality_or_voice_avatar_measured"]


@pytest.mark.parametrize("count,interval", [(0, 1), (121, 1), (True, 1),
                                           (1, -1), (1, float("nan")),
                                           (1, float("inf"))])
def test_invalid_sampling_budget_does_not_execute(tmp_path, monkeypatch, count, interval):
    attempted = []
    monkeypatch.setattr(probe, "_revision", lambda _: SHA)
    with pytest.raises(probe.HostObservationError):
        probe.observe_host(
            repo=tmp_path, expected_revision=SHA, declared_role="venus",
            scenario="idle", count=count, interval_seconds=interval,
            collector=lambda: attempted.append(1) or sensors(),
        )
    assert not attempted
