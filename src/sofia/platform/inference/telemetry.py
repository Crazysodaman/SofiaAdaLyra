"""Capacity and residency footprints for hardware-neutral inference admission.

Missing, stale or unmeasured telemetry is never treated as free capacity.  The
simulated sources here are deterministic test evidence only; they do not claim
live-host measurements.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock
from typing import Protocol, Sequence

from sofia.platform.ops.activity import ActivityMode


@dataclass(frozen=True, slots=True)
class ModelFootprint:
    """Weights + KV cache + runtime overhead + safety headroom, per generation."""

    weights_bytes: int
    kv_cache_bytes: int
    runtime_bytes: int
    safety_headroom_bytes: int
    simulated: bool
    measured: bool

    def __post_init__(self) -> None:
        for label, value in (
            ("weights_bytes", self.weights_bytes),
            ("kv_cache_bytes", self.kv_cache_bytes),
            ("runtime_bytes", self.runtime_bytes),
            ("safety_headroom_bytes", self.safety_headroom_bytes),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if self.weights_bytes < 1:
            raise ValueError("weights_bytes must be positive")
        if self.kv_cache_bytes < 1:
            raise ValueError("kv_cache_bytes must be positive")
        if type(self.simulated) is not bool or type(self.measured) is not bool:
            raise TypeError("footprint evidence flags must be booleans")

    @property
    def resident_bytes(self) -> int:
        return (
            self.weights_bytes + self.kv_cache_bytes
            + self.runtime_bytes + self.safety_headroom_bytes
        )

    @property
    def generation_bytes(self) -> int:
        return self.kv_cache_bytes + self.runtime_bytes + self.safety_headroom_bytes

    @property
    def evidence_level(self) -> str:
        if self.measured and not self.simulated:
            return "measured"
        if self.measured and self.simulated:
            return "simulated"
        return "unknown"


@dataclass(frozen=True, slots=True)
class HostCapacity:
    """One fresh-or-stale observed host capacity snapshot."""

    host_id: str
    observed_at: float
    expires_at: float
    vram_total_bytes: int
    vram_free_bytes: int
    ram_total_bytes: int
    ram_free_bytes: int
    gpu_utilization_percent: float
    activity: ActivityMode
    source: str
    simulated: bool
    measured: bool

    def __post_init__(self) -> None:
        if type(self.host_id) is not str or not self.host_id.strip():
            raise ValueError("host_id required")
        if type(self.observed_at) not in (int, float) or not math.isfinite(
            float(self.observed_at)
        ):
            raise ValueError("observed_at must be finite")
        if type(self.expires_at) not in (int, float) or not math.isfinite(
            float(self.expires_at)
        ):
            raise ValueError("expires_at must be finite")
        if float(self.expires_at) <= float(self.observed_at):
            raise ValueError("expires_at must follow observed_at")
        for label, value in (
            ("vram_total_bytes", self.vram_total_bytes),
            ("vram_free_bytes", self.vram_free_bytes),
            ("ram_total_bytes", self.ram_total_bytes),
            ("ram_free_bytes", self.ram_free_bytes),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{label} must be a non-negative integer")
        if self.vram_free_bytes > self.vram_total_bytes:
            raise ValueError("free VRAM cannot exceed total VRAM")
        if self.ram_free_bytes > self.ram_total_bytes:
            raise ValueError("free RAM cannot exceed total RAM")
        if type(self.gpu_utilization_percent) not in (int, float) or not (
            0.0 <= float(self.gpu_utilization_percent) <= 100.0
        ):
            raise ValueError("gpu utilization must be in 0..100")
        if not isinstance(self.activity, ActivityMode) or self.activity is ActivityMode.AUTO:
            raise ValueError("activity must be a concrete ActivityMode")
        if type(self.source) is not str or not self.source.strip():
            raise ValueError("source required")
        if type(self.simulated) is not bool or type(self.measured) is not bool:
            raise TypeError("capacity evidence flags must be booleans")

    def fresh(self, now: float) -> bool:
        moment = float(now)
        return float(self.observed_at) <= moment + 5.0 and float(self.expires_at) > moment

    @property
    def evidence_level(self) -> str:
        if self.measured and not self.simulated:
            return "measured"
        if self.measured and self.simulated:
            return "simulated"
        return "unknown"


@dataclass(frozen=True, slots=True)
class CapacityDecision:
    allowed: bool
    reason: str | None
    parallel_slots: int
    free_after_bytes: int | None
    fresh: bool
    evidence_level: str


def _validate_now(now: float) -> float:
    if type(now) not in (int, float) or not math.isfinite(float(now)):
        raise ValueError("now must be a finite number")
    return float(now)


def admit_generation(
    snapshot: HostCapacity,
    footprint: ModelFootprint,
    *,
    active_generations: int,
    max_parallel: int,
    now: float,
    already_resident: bool = True,
) -> CapacityDecision:
    """Admit one more generation only from fresh, measured capacity evidence."""
    if not isinstance(snapshot, HostCapacity):
        raise TypeError("snapshot must be HostCapacity")
    if not isinstance(footprint, ModelFootprint):
        raise TypeError("footprint must be ModelFootprint")
    if type(active_generations) is not int or active_generations < 0:
        raise ValueError("active_generations must be a non-negative integer")
    if type(max_parallel) is not int or max_parallel < 1:
        raise ValueError("max_parallel must be a positive integer")
    if type(already_resident) is not bool:
        raise TypeError("already_resident must be bool")
    moment = _validate_now(now)
    fresh = snapshot.fresh(moment)
    if not fresh:
        return CapacityDecision(
            False, "capacity telemetry is stale or unknown", 0, None, False,
            snapshot.evidence_level,
        )
    if not snapshot.measured:
        return CapacityDecision(
            False, "capacity is not measured", 0, None, True,
            snapshot.evidence_level,
        )
    generation = footprint.generation_bytes
    base = 0 if already_resident else footprint.resident_bytes
    if snapshot.vram_free_bytes < base:
        return CapacityDecision(
            False, "insufficient free VRAM for model residency", 0,
            snapshot.vram_free_bytes, True, snapshot.evidence_level,
        )
    remaining = snapshot.vram_free_bytes - base
    usable_slots = 1 + remaining // generation
    slots = min(max_parallel, usable_slots)
    if slots < 1:
        return CapacityDecision(
            False, "insufficient free VRAM for one generation", 0,
            snapshot.vram_free_bytes, True, snapshot.evidence_level,
        )
    if active_generations >= slots:
        return CapacityDecision(
            False, "capacity parallelism is saturated", slots,
            snapshot.vram_free_bytes, True, snapshot.evidence_level,
        )
    first_required = generation if already_resident else footprint.resident_bytes
    return CapacityDecision(
        True, None, slots, snapshot.vram_free_bytes - first_required, True,
        snapshot.evidence_level,
    )


def effective_parallelism(
    snapshot: HostCapacity,
    footprint: ModelFootprint,
    *,
    active_generations: int,
    requested_max: int,
    now: float,
    already_resident: bool = True,
) -> int:
    """Return 1 or 2 only when measured capacity supports it, else zero."""
    decision = admit_generation(
        snapshot, footprint, active_generations=active_generations,
        max_parallel=requested_max, now=now,
        already_resident=already_resident,
    )
    return decision.parallel_slots if decision.allowed else 0


def verified_idle(snapshot: HostCapacity, now: float) -> bool:
    """Idle requires fresh, measured, non-gaming evidence; unknown is not idle."""
    if not isinstance(snapshot, HostCapacity):
        raise TypeError("snapshot must be HostCapacity")
    return (
        snapshot.fresh(_validate_now(now))
        and snapshot.measured
        and snapshot.activity is ActivityMode.IDLE
    )


class CapacitySource(Protocol):
    def snapshot(self, now: float) -> HostCapacity:
        ...


class StaticCapacitySource:
    """One deterministic snapshot for scheduler tests."""

    def __init__(self, snapshot: HostCapacity) -> None:
        if not isinstance(snapshot, HostCapacity):
            raise TypeError("snapshot must be HostCapacity")
        self._snapshot = snapshot
        self._lock = RLock()

    def snapshot(self, now: float) -> HostCapacity:
        _validate_now(now)
        with self._lock:
            return self._snapshot

    def replace(self, snapshot: HostCapacity) -> None:
        if not isinstance(snapshot, HostCapacity):
            raise TypeError("snapshot must be HostCapacity")
        with self._lock:
            self._snapshot = snapshot


class SequenceCapacitySource:
    """Deterministic snapshot sequence; the last snapshot repeats."""

    def __init__(self, snapshots: Sequence[HostCapacity]) -> None:
        if not isinstance(snapshots, (tuple, list)) or not snapshots or any(
            not isinstance(item, HostCapacity) for item in snapshots
        ):
            raise ValueError("snapshots must be a nonempty sequence of HostCapacity")
        self._snapshots = tuple(snapshots)
        self._index = 0
        self._lock = RLock()

    def snapshot(self, now: float) -> HostCapacity:
        _validate_now(now)
        with self._lock:
            index = min(self._index, len(self._snapshots) - 1)
            self._index += 1
            return self._snapshots[index]
