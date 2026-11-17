"""Benchmark profile support for one shared exact model.

Simulated measurements are deterministic test evidence.  Real measurements are
accepted only through an explicit approval object and a caller-supplied runner;
this module never invents a digest, latency, VRAM figure or host result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from .contract import CapacityDenied, EvidenceLevel, ModelIdentity
from .telemetry import HostCapacity, ModelFootprint

SHARED_CONTEXT_TOKENS = 4096
SHARED_MODEL_FAMILY = "qwen3.5:9b"


def _number(value: float, label: str) -> float:
    if type(value) not in (int, float) or float(value) < 0:
        raise ValueError(f"{label} must be non-negative")
    return float(value)


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    model: ModelIdentity
    context_tokens: int = SHARED_CONTEXT_TOKENS
    max_loaded_models: int = 1
    parallelism_candidates: tuple[int, ...] = (1, 2)
    keep_alive_seconds: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if type(self.context_tokens) is not int or self.context_tokens < 1:
            raise ValueError("context_tokens must be positive")
        if self.max_loaded_models != 1:
            raise ValueError("the shared benchmark profile keeps one loaded model")
        if (
            type(self.parallelism_candidates) is not tuple
            or not self.parallelism_candidates
            or any(
                type(item) is not int or item not in (1, 2)
                for item in self.parallelism_candidates
            )
        ) or self.parallelism_candidates[0] != 1:
            raise ValueError("parallelism candidates must start with one")
        if self.keep_alive_seconds is not None and (
            type(self.keep_alive_seconds) not in (int, float)
            or float(self.keep_alive_seconds) < 0
        ):
            raise ValueError("keep_alive_seconds must be non-negative or None")


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    parallelism: int
    time_to_first_token_ms: float
    tokens_per_second: float
    total_latency_ms: float
    footprint: ModelFootprint
    peak_vram_bytes: int
    host_ram_bytes: int
    gpu_utilization_percent: float
    game_impact_ms: float | None
    evidence_level: EvidenceLevel

    def __post_init__(self) -> None:
        if self.parallelism not in (1, 2):
            raise ValueError("parallelism must be 1 or 2")
        _number(self.time_to_first_token_ms, "time_to_first_token_ms")
        _number(self.tokens_per_second, "tokens_per_second")
        _number(self.total_latency_ms, "total_latency_ms")
        if not isinstance(self.footprint, ModelFootprint):
            raise TypeError("footprint must be ModelFootprint")
        for label, value in (
            ("peak_vram_bytes", self.peak_vram_bytes),
            ("host_ram_bytes", self.host_ram_bytes),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if type(self.gpu_utilization_percent) not in (int, float) or not (
            0.0 <= float(self.gpu_utilization_percent) <= 100.0
        ):
            raise ValueError("gpu_utilization_percent must be in 0..100")
        if self.game_impact_ms is not None:
            _number(self.game_impact_ms, "game_impact_ms")
        if not isinstance(self.evidence_level, EvidenceLevel):
            raise TypeError("evidence_level must be EvidenceLevel")


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    profile: BenchmarkProfile
    host_id: str
    measurements: tuple[BenchmarkMeasurement, ...]
    evidence_level: EvidenceLevel
    loaded_models: int
    load_count: int
    unload_count: int
    approved_real_host: bool

    def __post_init__(self) -> None:
        if self.loaded_models != 1:
            raise ValueError("benchmark report must account for one loaded model")
        if type(self.approved_real_host) is not bool:
            raise TypeError("approved_real_host must be bool")

    def measurement_for(self, parallelism: int) -> BenchmarkMeasurement | None:
        for measurement in self.measurements:
            if measurement.parallelism == parallelism:
                return measurement
        return None


@dataclass(frozen=True, slots=True)
class RealBenchmarkApproval:
    """Explicit owner approval reference for one named enrolled host."""

    host_id: str
    approved_by: str
    reference: str
    approved_at: datetime

    def __post_init__(self) -> None:
        for label, value, maximum in (
            ("host_id", self.host_id, 160),
            ("approved_by", self.approved_by, 160),
            ("reference", self.reference, 256),
        ):
            if type(value) is not str or not value.strip() or len(value) > maximum:
                raise ValueError(f"{label} must be bounded nonempty text")
        if not isinstance(self.approved_at, datetime) or (
            self.approved_at.tzinfo is None or self.approved_at.utcoffset() is None
        ):
            raise ValueError("approved_at must be timezone-aware")


def _required_vram(profile: BenchmarkProfile, measurement: BenchmarkMeasurement) -> int:
    # Weights are shared by concurrent generations of the same exact model; each
    # additional generation needs its own KV/runtime/headroom budget.
    return (
        measurement.footprint.resident_bytes
        + (measurement.parallelism - 1) * measurement.footprint.generation_bytes
    )


class SharedModelBenchmarkHarness:
    """Validate and report profile measurements without filling unknowns."""

    def __init__(
        self, profile: BenchmarkProfile, capacity: HostCapacity, *,
        load_count: int = 1, unload_count: int = 0,
    ) -> None:
        if not isinstance(profile, BenchmarkProfile):
            raise TypeError("profile must be BenchmarkProfile")
        if not isinstance(capacity, HostCapacity):
            raise TypeError("capacity must be HostCapacity")
        if type(load_count) is not int or load_count < 0:
            raise ValueError("load_count must be non-negative")
        if type(unload_count) is not int or unload_count < 0:
            raise ValueError("unload_count must be non-negative")
        self.profile = profile
        self.capacity = capacity
        self.load_count = load_count
        self.unload_count = unload_count

    def _validate_measurement(
        self, measurement: BenchmarkMeasurement, now: float,
    ) -> None:
        if measurement.parallelism not in self.profile.parallelism_candidates:
            raise ValueError("measurement uses an unsupported parallelism profile")
        required = _required_vram(self.profile, measurement)
        if not self.capacity.fresh(now):
            raise CapacityDenied("benchmark capacity telemetry is stale or unknown")
        if not self.capacity.measured:
            raise CapacityDenied("benchmark capacity is not measured")
        if required > self.capacity.vram_free_bytes:
            raise CapacityDenied(
                "measured free VRAM does not support this parallelism profile"
            )
        if measurement.peak_vram_bytes > self.capacity.vram_total_bytes:
            raise CapacityDenied("measured peak VRAM exceeds total device VRAM")
        if measurement.evidence_level is not EvidenceLevel.SIMULATED:
            raise ValueError(
                "simulated harness accepts only simulated evidence; use run_real"
            )

    def simulate(
        self, measurements: Sequence[BenchmarkMeasurement], *, now: float,
    ) -> BenchmarkReport:
        prepared = tuple(measurements)
        if not prepared:
            raise ValueError("at least one benchmark measurement is required")
        for measurement in prepared:
            if not isinstance(measurement, BenchmarkMeasurement):
                raise TypeError("measurements must contain BenchmarkMeasurement")
            self._validate_measurement(measurement, now)
        if self.load_count != 1:
            raise ValueError("shared benchmark must account for exactly one model load")
        return BenchmarkReport(
            profile=self.profile,
            host_id=self.capacity.host_id,
            measurements=prepared,
            evidence_level=EvidenceLevel.SIMULATED,
            loaded_models=1,
            load_count=self.load_count,
            unload_count=self.unload_count,
            approved_real_host=False,
        )

    def run_real(
        self, *, approval: RealBenchmarkApproval,
        runner: Callable[[BenchmarkProfile], Sequence[BenchmarkMeasurement]],
        now: float,
    ) -> BenchmarkReport:
        if not isinstance(approval, RealBenchmarkApproval):
            raise PermissionError(
                "real benchmark requires an explicit owner approval reference"
            )
        if approval.host_id != self.capacity.host_id:
            raise PermissionError("benchmark approval is for a different host")
        if self.capacity.simulated or not self.capacity.measured:
            raise PermissionError(
                "real benchmark requires measured non-simulated host capacity"
            )
        if not callable(runner):
            raise TypeError("runner must be callable")
        measurements = tuple(runner(self.profile))
        if not measurements or any(
            not isinstance(item, BenchmarkMeasurement) for item in measurements
        ):
            raise RuntimeError("real benchmark runner produced no measurements")
        for measurement in measurements:
            if measurement.evidence_level is not EvidenceLevel.OBSERVED:
                raise RuntimeError(
                    "real benchmark runner did not produce observed evidence"
                )
            if measurement.parallelism not in self.profile.parallelism_candidates:
                raise ValueError("measurement uses an unsupported parallelism profile")
            required = _required_vram(self.profile, measurement)
            if not self.capacity.fresh(now):
                raise CapacityDenied("benchmark capacity telemetry is stale or unknown")
            if required > self.capacity.vram_free_bytes:
                raise CapacityDenied(
                    "measured free VRAM does not support this parallelism profile"
                )
        return BenchmarkReport(
            profile=self.profile,
            host_id=self.capacity.host_id,
            measurements=measurements,
            evidence_level=EvidenceLevel.OBSERVED,
            loaded_models=1,
            load_count=self.load_count,
            unload_count=self.unload_count,
            approved_real_host=True,
        )
