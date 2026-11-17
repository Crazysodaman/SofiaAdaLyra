"""Exact-model residency accounting with no implicit download or substitution."""
from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock
from typing import Iterable

from .contract import (
    CapacityDenied, ModelIdentity, ModelNotInstalled, ModelResidencyError,
)
from .telemetry import HostCapacity, ModelFootprint


class ModelLoadDeferred(ModelResidencyError):
    """Loading this model is refused by the current activity policy."""


@dataclass(frozen=True, slots=True)
class ResidencyRecord:
    model: ModelIdentity
    footprint: ModelFootprint
    loaded_at: float
    last_used_at: float
    keep_alive_seconds: float | None
    active_generations: int


@dataclass(frozen=True, slots=True)
class ResidencyTelemetry:
    host_id: str | None
    loaded: tuple[ModelIdentity, ...]
    load_count: int
    unload_count: int
    refused_loads: int
    events: tuple[tuple[str, str, float], ...]


@dataclass(slots=True)
class _Loaded:
    model: ModelIdentity
    footprint: ModelFootprint
    loaded_at: float
    last_used_at: float
    keep_alive_seconds: float | None
    active_generations: int = 0


def _now(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError("now must be a finite number")
    return float(value)


class ModelResidencyTracker:
    """Track only explicitly installed exact models on one backend host."""

    def __init__(
        self, installed: Iterable[ModelIdentity], *,
        max_loaded_models: int = 1, event_limit: int = 64,
    ) -> None:
        models = tuple(installed)
        if any(not isinstance(model, ModelIdentity) for model in models):
            raise TypeError("installed must contain ModelIdentity values")
        if type(max_loaded_models) is not int or max_loaded_models < 1:
            raise ValueError("max_loaded_models must be positive")
        if type(event_limit) is not int or event_limit < 1:
            raise ValueError("event_limit must be positive")
        self._installed = frozenset(models)
        self._max_loaded = max_loaded_models
        self._event_limit = event_limit
        self._lock = RLock()
        self._loaded: dict[ModelIdentity, _Loaded] = {}
        self._load_count = 0
        self._unload_count = 0
        self._refused = 0
        self._events: list[tuple[str, str, float]] = []
        self._host_id: str | None = None

    def _record_event(self, kind: str, model: ModelIdentity, now: float) -> None:
        self._events.append((kind, model.label, now))
        if len(self._events) > self._event_limit:
            self._events.pop(0)

    def is_installed(self, model: ModelIdentity) -> bool:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        return model in self._installed

    @property
    def installed(self) -> tuple[ModelIdentity, ...]:
        return tuple(sorted(self._installed, key=lambda item: item.label))

    @property
    def loaded(self) -> tuple[ModelIdentity, ...]:
        with self._lock:
            return tuple(self._loaded)

    def record(self, model: ModelIdentity) -> ResidencyRecord:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        with self._lock:
            loaded = self._loaded.get(model)
            if loaded is None:
                raise ModelResidencyError("model is not currently loaded")
            return ResidencyRecord(
                loaded.model, loaded.footprint, loaded.loaded_at,
                loaded.last_used_at, loaded.keep_alive_seconds,
                loaded.active_generations,
            )

    def ensure_loaded(
        self, model: ModelIdentity, footprint: ModelFootprint,
        capacity: HostCapacity, now: float, *,
        allow_load: bool = True,
        keep_alive_seconds: float | None = None,
    ) -> ResidencyRecord:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        if not isinstance(footprint, ModelFootprint):
            raise TypeError("footprint must be ModelFootprint")
        if not isinstance(capacity, HostCapacity):
            raise TypeError("capacity must be HostCapacity")
        moment = _now(now)
        if keep_alive_seconds is not None and (
            type(keep_alive_seconds) not in (int, float)
            or float(keep_alive_seconds) < 0
        ):
            raise ValueError("keep_alive_seconds must be non-negative or None")
        with self._lock:
            if model not in self._installed:
                raise ModelNotInstalled(
                    "exact model is not installed; downloads are not authorized"
                )
            existing = self._loaded.get(model)
            if existing is not None:
                if existing.footprint != footprint:
                    raise ModelResidencyError(
                        "a loaded model footprint cannot change without unload"
                    )
                existing.last_used_at = moment
                return self.record(model)
            if not allow_load:
                self._refused += 1
                raise ModelLoadDeferred("model load is deferred by activity policy")
            if len(self._loaded) >= self._max_loaded:
                self._refused += 1
                raise ModelResidencyError(
                    "loaded model limit reached; active models are not evicted"
                )
            if not capacity.fresh(moment):
                self._refused += 1
                raise CapacityDenied("capacity telemetry is stale or unknown")
            if not footprint.measured:
                self._refused += 1
                raise CapacityDenied("model footprint is not measured")
            if footprint.resident_bytes > capacity.vram_free_bytes:
                self._refused += 1
                raise CapacityDenied("insufficient free VRAM for model residency")
            loaded = _Loaded(
                model, footprint, moment, moment,
                None if keep_alive_seconds is None else float(keep_alive_seconds),
            )
            self._loaded[model] = loaded
            self._load_count += 1
            self._host_id = capacity.host_id
            self._record_event("load", model, moment)
            return ResidencyRecord(
                loaded.model, loaded.footprint, loaded.loaded_at,
                loaded.last_used_at, loaded.keep_alive_seconds,
                loaded.active_generations,
            )

    def begin_generation(self, model: ModelIdentity, now: float) -> None:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        moment = _now(now)
        with self._lock:
            loaded = self._loaded.get(model)
            if loaded is None:
                raise ModelResidencyError("generation requires a resident model")
            loaded.active_generations += 1
            loaded.last_used_at = moment

    def end_generation(self, model: ModelIdentity, now: float) -> None:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        moment = _now(now)
        with self._lock:
            loaded = self._loaded.get(model)
            if loaded is None:
                raise ModelResidencyError("generation ended without a resident model")
            if loaded.active_generations < 1:
                raise ModelResidencyError("no active generation to end")
            loaded.active_generations -= 1
            loaded.last_used_at = moment

    def touch(self, model: ModelIdentity, now: float) -> None:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        moment = _now(now)
        with self._lock:
            loaded = self._loaded.get(model)
            if loaded is None:
                raise ModelResidencyError("model is not currently loaded")
            loaded.last_used_at = moment

    def unload(self, model: ModelIdentity, now: float) -> bool:
        if not isinstance(model, ModelIdentity):
            raise TypeError("model must be ModelIdentity")
        moment = _now(now)
        with self._lock:
            loaded = self._loaded.get(model)
            if loaded is None:
                return False
            if loaded.active_generations > 0:
                raise ModelResidencyError(
                    "active generation prevents model unload"
                )
            del self._loaded[model]
            self._unload_count += 1
            self._record_event("unload", model, moment)
            return True

    def reclaim(self, now: float) -> tuple[ModelIdentity, ...]:
        """Unload keep-alive-expired idle models; never an active session."""
        moment = _now(now)
        reclaimed: list[ModelIdentity] = []
        with self._lock:
            for model, loaded in tuple(self._loaded.items()):
                if loaded.active_generations > 0:
                    continue
                keep_alive = loaded.keep_alive_seconds
                if keep_alive is None:
                    continue
                if moment - loaded.last_used_at < keep_alive:
                    continue
                del self._loaded[model]
                self._unload_count += 1
                self._record_event("unload", model, moment)
                reclaimed.append(model)
        return tuple(reclaimed)

    def telemetry(self) -> ResidencyTelemetry:
        with self._lock:
            return ResidencyTelemetry(
                self._host_id,
                tuple(self._loaded),
                self._load_count,
                self._unload_count,
                self._refused,
                tuple(self._events),
            )
