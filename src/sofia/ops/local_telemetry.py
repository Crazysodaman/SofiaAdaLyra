"""Local normalized telemetry collection for Fleet agents.

Unsupported metrics remain None. Collection is read-only and returns the same
HostTelemetry contract used by OPS persistence and placement.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any

from .model import HostTelemetry


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("telemetry numeric value cannot be boolean")
    result = float(value)
    return result


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("telemetry numeric value cannot be boolean")
    return int(value)


def _run_powershell(command: str) -> str:
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout


def _windows_snapshot(runner=_run_powershell) -> dict[str, Any]:
    command = (
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "$cpu = Get-CimInstance Win32_Processor | "
        "Measure-Object -Property LoadPercentage -Average; "
        "$disk = Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
        "Measure-Object -Property FreeSpace -Sum; "
        "[PSCustomObject]@{"
        "CpuPercent = $cpu.Average;"
        "RamTotalBytes = [int64]$os.TotalVisibleMemorySize * 1024;"
        "RamUsedBytes = ([int64]$os.TotalVisibleMemorySize - "
        "[int64]$os.FreePhysicalMemory) * 1024;"
        "StorageFreeBytes = [int64]$disk.Sum"
        "} | ConvertTo-Json -Compress"
    )
    raw = runner(command)
    payload = json.loads(raw) if raw.strip() else None
    if not isinstance(payload, dict):
        raise ValueError("Windows telemetry returned invalid JSON")
    return payload



def _windows_nvidia_gpu_snapshot(*, runner=None) -> dict[str, int | float] | None:
    """Observe ONE physical NVIDIA GPU, not a summed fictitious VRAM pool.

    NVIDIA's local read-only CLI returns MiB. Aggregate VRAM from multiple
    cards must not be advertised as one GPU capable of hosting a model.
    Unknown, malformed, unavailable and timeout all remain None.
    """
    import os

    executable = shutil.which("nvidia-smi")
    if executable is None:
        root = os.environ.get("ProgramFiles", "")
        fixed = Path(root) / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe"
        executable = str(fixed) if root and fixed.is_file() else None
    if executable is None:
        return None
    argv = (
        executable, "--query-gpu=memory.total,memory.used,utilization.gpu",
        "--format=csv,noheader,nounits",
    )
    try:
        if runner is None:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=6, check=True,
            )
            output = completed.stdout
        else:
            output = runner(argv)
        if not isinstance(output, str) or len(output) > 4096:
            return None
        lines = output.strip().splitlines()
        if not 1 <= len(lines) <= 8:
            return None
        cards = []
        for line in lines:
            parts = [item.strip() for item in line.split(",")]
            if len(parts) != 3:
                return None
            total, used, percent = (int(item) for item in parts)
            if (
                not 0 < total <= 1048576 or not 0 <= used <= total
                or not 0 <= percent <= 100
            ):
                return None
            cards.append((total - used, total, used, percent))
        # The selected GPU represents a single independent placement target.
        # Prefer greatest free VRAM, then lower utilization.
        free, total, used, percent = max(
            cards, key=lambda card: (card[0], -card[3])
        )
        mib = 1024 * 1024
        return {
            "gpu_percent": float(percent),
            "vram_total_bytes": total * mib,
            "vram_used_bytes": used * mib,
        }
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        return None


def _linux_meminfo(path: Path = Path("/proc/meminfo")) -> tuple[int | None, int | None]:
    if not path.is_file():
        return None, None
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        try:
            amount = int(parts[0])
        except ValueError:
            continue
        multiplier = 1024 if len(parts) > 1 and parts[1].casefold() == "kb" else 1
        values[key] = amount * multiplier
    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    used = None if total is None or available is None else max(0, total - available)
    return used, total


def _linux_cpu_percent(path: Path = Path("/proc/stat")) -> float | None:
    if not path.is_file():
        return None
    first = path.read_text(encoding="utf-8", errors="replace").splitlines()
    line = next((item for item in first if item.startswith("cpu ")), None)
    if line is None:
        return None
    parts = line.split()[1:]
    try:
        numbers = [int(value) for value in parts]
    except ValueError:
        return None
    if len(numbers) < 4:
        return None
    total = sum(numbers)
    idle = numbers[3] + (numbers[4] if len(numbers) > 4 else 0)
    # This is cumulative-since-boot utilization, intentionally bounded and
    # honest. A later sampler can retain deltas for interval utilization.
    if total <= 0:
        return None
    return max(0.0, min(100.0, (total - idle) * 100.0 / total))


def _linux_temperature() -> float | None:
    root = Path("/sys/class/thermal")
    if not root.is_dir():
        return None
    for candidate in sorted(root.glob("thermal_zone*/temp")):
        try:
            raw = float(candidate.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        value = raw / 1000.0 if raw > 1000 else raw
        if -50.0 <= value <= 200.0:
            return value
    return None


def _linux_throttled() -> bool | None:
    executable = shutil.which("vcgencmd")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "get_throttled"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = completed.stdout.strip().casefold()
    if "0x" not in text:
        return None
    try:
        value = int(text.rsplit("0x", 1)[1], 16)
    except ValueError:
        return None
    return value != 0


def collect_local_telemetry() -> HostTelemetry:
    observed_at = datetime.now(timezone.utc)
    system = platform.system()

    if system == "Windows":
        payload = _windows_snapshot()
        nvidia = _windows_nvidia_gpu_snapshot()
        return HostTelemetry(
            observed_at=observed_at,
            cpu_percent=_optional_float(payload.get("CpuPercent")),
            ram_used_bytes=_optional_int(payload.get("RamUsedBytes")),
            ram_total_bytes=_optional_int(payload.get("RamTotalBytes")),
            storage_free_bytes=_optional_int(payload.get("StorageFreeBytes")),
            gpu_percent=None if nvidia is None else nvidia["gpu_percent"],
            vram_total_bytes=None if nvidia is None else nvidia["vram_total_bytes"],
            vram_used_bytes=None if nvidia is None else nvidia["vram_used_bytes"],
        )

    if system == "Linux":
        ram_used, ram_total = _linux_meminfo()
        try:
            storage_free = shutil.disk_usage("/").free
        except OSError:
            storage_free = None
        return HostTelemetry(
            observed_at=observed_at,
            cpu_percent=_linux_cpu_percent(),
            ram_used_bytes=ram_used,
            ram_total_bytes=ram_total,
            storage_free_bytes=storage_free,
            temperature_c=_linux_temperature(),
            throttled=_linux_throttled(),
        )

    return HostTelemetry(observed_at=observed_at)
