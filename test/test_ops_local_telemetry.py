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

    monkeypatch.setattr(telemetry_module, "_windows_nvidia_gpu_snapshot", lambda: None)
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



def test_windows_3060_gpu_snapshot_reports_real_single_gpu_bytes(monkeypatch):
    monkeypatch.setattr(
        telemetry_module.shutil, "which",
        lambda name: r"C:\\Program Files\\NVIDIA Corporation\\NVSMI\\nvidia-smi.exe",
    )
    observed = telemetry_module._windows_nvidia_gpu_snapshot(
        runner=lambda argv: "8192, 1024, 13\n",
    )
    assert observed == {
        "gpu_percent": 13.0,
        "vram_total_bytes": 8192 * 1024 * 1024,
        "vram_used_bytes": 1024 * 1024 * 1024,
    }


def test_windows_nvidia_capacity_never_sums_two_separate_gpu_cards(monkeypatch):
    monkeypatch.setattr(telemetry_module.shutil, "which", lambda _: "nvidia-smi")
    observed = telemetry_module._windows_nvidia_gpu_snapshot(
        runner=lambda argv: "8192, 4096, 40\n4096, 0, 5\n",
    )
    assert observed["vram_total_bytes"] == 4096 * 1024 * 1024
    assert observed["vram_used_bytes"] == 0


@pytest.mark.parametrize("raw", [
    "", "N/A, N/A, N/A\n", "8192, 9500, 12\n",
    "8192, 1024, 101\n", "-1, 0, 0\n", "8192, 1024\n",
    "8192, 1024, 12\n" * 9,
])
def test_nvidia_unavailable_or_invalid_metrics_are_unknown_not_vram(raw, monkeypatch):
    monkeypatch.setattr(telemetry_module.shutil, "which", lambda _: "nvidia-smi")
    assert telemetry_module._windows_nvidia_gpu_snapshot(
        runner=lambda argv: raw,
    ) is None


def test_live_windows_telemetry_presents_nvidia_values_without_reaching_host(monkeypatch):
    monkeypatch.setattr(telemetry_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        telemetry_module, "_windows_snapshot",
        lambda: {
            "CpuPercent": 22, "RamUsedBytes": 8*1024**3,
            "RamTotalBytes": 32*1024**3,
            "StorageFreeBytes": 500*1024**3,
        },
    )
    monkeypatch.setattr(
        telemetry_module, "_windows_nvidia_gpu_snapshot",
        lambda: {
            "gpu_percent": 15.0,
            "vram_total_bytes": 8*1024**3,
            "vram_used_bytes": 1*1024**3,
        },
    )
    report = collect_local_telemetry()
    assert report.ram_total_bytes == 32 * 1024**3
    assert report.vram_total_bytes == 8 * 1024**3
    assert report.vram_used_bytes == 1 * 1024**3
    assert report.gpu_percent == 15.0
