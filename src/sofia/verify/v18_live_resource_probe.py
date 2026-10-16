"""CA-002/007, CA-906/911: explicit, read-only host resource observations.

Invoke on the intended machine; this tool never launches Sofía, starts model
inference, enumerates process arguments, captures screens, or claims that
a user-declared activity label was independently verified. In particular,
system load is NOT represented as Sofía's per-process consumption.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

_METRICS = (
    "system_cpu_percent", "system_ram_used_bytes", "system_ram_total_bytes",
    "gpu_utilization_percent", "gpu_vram_used_mib", "gpu_vram_total_mib",
    "gpu_power_watts",
)
_SCENARIOS = frozenset({"idle", "gaming", "conversation", "startup", "other"})
_ROLES = frozenset({"venus", "artemis", "other"})


class HostObservationError(ValueError):
    """Missing, mismatched or untrustworthy host measurement input."""


def _revision(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repo, capture_output=True, text=True, check=True, timeout=10,
    )
    sha = result.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise HostObservationError("host probe requires exact Git SHA")
    return sha


def _gpu_metrics() -> dict[str, float | None]:
    metrics = {name: None for name in _METRICS[3:]}
    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip().splitlines()
        if len(output) != 1:
            return metrics   # multiple GPUs: never silently mix devices
        values = [float(item.strip()) for item in output[0].split(",")]
        if len(values) != 4 or any(not math.isfinite(v) or v < 0 for v in values):
            return metrics
        keys = tuple(metrics)
        for key, value in zip(keys, values, strict=True):
            metrics[key] = value
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return metrics


def measure_once() -> dict[str, float | int | None]:
    """Read global host load when supported; missing sensors remain None."""
    metrics: dict[str, float | int | None] = {name: None for name in _METRICS}
    try:
        import psutil
        metrics["system_cpu_percent"] = psutil.cpu_percent(interval=0.05)
        mem = psutil.virtual_memory()
        metrics["system_ram_used_bytes"] = mem.used
        metrics["system_ram_total_bytes"] = mem.total
    except (ImportError, OSError):
        pass
    metrics.update(_gpu_metrics())
    return metrics


def _validated(raw: object) -> dict[str, float | int | None]:
    if not isinstance(raw, dict) or set(raw) != set(_METRICS):
        raise HostObservationError("incomplete or ambiguous host sensor record")
    cleaned: dict[str, float | int | None] = {}
    for metric in _METRICS:
        value = raw[metric]
        if value is None:
            cleaned[metric] = None
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise HostObservationError("invalid sensor metric " + metric)
        if metric.endswith("_percent") and value > 100:
            raise HostObservationError("sensor percentage out of range")
        cleaned[metric] = value
    if (cleaned["system_ram_total_bytes"] is not None
            and cleaned["system_ram_used_bytes"] is not None
            and cleaned["system_ram_used_bytes"] > cleaned["system_ram_total_bytes"]):
        raise HostObservationError("used system RAM exceeds observed total")
    if (cleaned["gpu_vram_total_mib"] is not None
            and cleaned["gpu_vram_used_mib"] is not None
            and cleaned["gpu_vram_used_mib"] > cleaned["gpu_vram_total_mib"]):
        raise HostObservationError("used VRAM exceeds observed GPU total")
    return cleaned


def observe_host(
    *,
    repo: Path,
    expected_revision: str,
    declared_role: str,
    scenario: str,
    count: int,
    interval_seconds: float,
    collector=measure_once,
    pause=time.sleep,
    clock=lambda: datetime.now(timezone.utc),
) -> dict:
    """Bounded, actively requested sampling, with no implied host attestation."""
    if declared_role not in _ROLES or scenario not in _SCENARIOS:
        raise HostObservationError("unsupported declared host role or scenario")
    if type(count) is not int or not 1 <= count <= 120:
        raise HostObservationError("sample count must be 1..120")
    if type(interval_seconds) not in (float, int) or not (
        math.isfinite(interval_seconds) and 0 <= interval_seconds <= 60
    ):
        raise HostObservationError("sampling interval must be 0..60 seconds")
    root = repo.resolve(strict=True)
    if _revision(root) != expected_revision:
        raise HostObservationError("checked-out revision does not match requested SHA")
    entries = []
    for index in range(count):
        if index:
            pause(interval_seconds)
        observed = clock()
        if (not isinstance(observed, datetime)
                or observed.tzinfo is None or observed.utcoffset() is None):
            raise HostObservationError("UTC-aware observation timestamp required")
        entries.append({
            "observed_at": observed.astimezone(timezone.utc).isoformat(),
            "sensors": _validated(collector()),
        })
    if _revision(root) != expected_revision:
        raise HostObservationError("Git HEAD changed during host observation")
    distributions = {}
    for metric in _METRICS:
        observed = sorted(e["sensors"][metric] for e in entries
                          if e["sensors"][metric] is not None)
        distributions[metric] = (
            {
                "observed_samples": len(observed),
                "min": observed[0],
                "p50": observed[math.ceil(0.50 * len(observed)) - 1],
                "p95": observed[math.ceil(0.95 * len(observed)) - 1],
                "max": observed[-1],
            } if observed else {
                "observed_samples": 0, "min": None, "p50": None,
                "p95": None, "max": None,
            }
        )
    return {
        "schema": "sofia.v18-live-resource-observation-v1",
        "source_commit": expected_revision,
        "declared_host_role": declared_role,
        "actual_platform": platform.system().casefold(),
        "declared_scenario": scenario,
        "scenario_independently_verified": False,
        "device_identity_independently_verified": False,
        "sofia_process_resource_attribution": False,
        "application_quality_or_voice_avatar_measured": False,
        "gate4_acceptance": False,
        "sample_count": count,
        "metric_scope": "global host, optional single NVIDIA GPU",
        "samples": entries,
        "summary": distributions,
        "warnings": [
            "Scenario and host role are operator-declared, not authenticated.",
            "Host resource use is not Sofía process resource consumption.",
            "No GPU sensor means unknown, not zero.",
            "Measurements do not establish task, soak, avatar or voice acceptance.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--host-role", required=True, choices=sorted(_ROLES))
    parser.add_argument("--scenario", required=True, choices=sorted(_SCENARIOS))
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = observe_host(
            repo=args.repo, expected_revision=args.expected_revision,
            declared_role=args.host_role, scenario=args.scenario,
            count=args.samples, interval_seconds=args.interval_seconds,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("resource_samples=" + str(report["sample_count"]) +
              " missing=" + str(sum(
                  x["observed_samples"] == 0 for x in report["summary"].values()
              )))
        return 0
    except (HostObservationError, OSError, subprocess.SubprocessError) as exc:
        print("host resource observation rejected: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
