from pathlib import Path

import pytest

import sofia.ops.local_telemetry as telemetry_module
from sofia.ops.local_telemetry import (
    _linux_cpu_percent,
    _linux_meminfo,
    collect_local_telemetry,
)


def test_windows_telemetry_normalizes_cpu_ram_and_storage(monkeypatch):
    monkeypatch.setattr(telemetry_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        telemetry_module,
        "_windows_snapshot",
        lambda: {
            "CpuPercent": 37.5,
            "RamUsedBytes": 8_000_000_000,
            "RamTotalBytes": 16_000_000_000,
            "StorageFreeBytes": 500_000_000_000,
        },
    )

    result = collect_local_telemetry()

    assert result.cpu_percent == 37.5
    assert result.ram_used_bytes == 8_000_000_000
    assert result.ram_total_bytes == 16_000_000_000
    assert result.storage_free_bytes == 500_000_000_000
    assert result.gpu_percent is None
    assert result.temperature_c is None


def test_linux_meminfo_uses_available_memory(tmp_path):
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(
        "MemTotal:       1000000 kB\n"
        "MemAvailable:    250000 kB\n",
        encoding="utf-8",
    )

    used, total = _linux_meminfo(meminfo)

    assert total == 1_024_000_000
    assert used == 768_000_000


def test_linux_cpu_percent_is_bounded_from_proc_stat(tmp_path):
    stat = tmp_path / "stat"
    stat.write_text("cpu  100 0 50 850 0 0 0 0 0 0\n", encoding="utf-8")

    assert _linux_cpu_percent(stat) == pytest.approx(15.0)


def test_unsupported_platform_returns_unknown_metrics(monkeypatch):
    monkeypatch.setattr(telemetry_module.platform, "system", lambda: "Plan9")

    result = collect_local_telemetry()

    assert result.cpu_percent is None
    assert result.ram_used_bytes is None
    assert result.ram_total_bytes is None
    assert result.storage_free_bytes is None
    assert result.temperature_c is None
    assert result.throttled is None
