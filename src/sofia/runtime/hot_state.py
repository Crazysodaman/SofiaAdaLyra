"""Bounded, revision-aware projections of trusted runtime state.

HotState is deliberately not an authority store.  Every value names the
canonical source and revision from which it was projected and expires unless
that source publishes a newer observation.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Condition, RLock
from typing import Generic, TypeVar

from sofia.cognition.performance import record_cache


T = TypeVar("T")


@dataclass(frozen=True)
class HotStateEntry(Generic[T]):
    value: T
    revision: int
    observed_at: datetime
    expires_at: datetime
    source: str

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        for name, value in (
            ("observed_at", self.observed_at), ("expires_at", self.expires_at),
        ):
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be after observed_at")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be nonempty")


@dataclass(frozen=True)
class HotStateStats:
    hits: int
    misses: int
    expirations: int
    entries: int


class HotState:
    """Small thread-safe LRU projection with event-driven change waiting."""

    def __init__(self, *, capacity: int = 128) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._entries: OrderedDict[str, HotStateEntry[object]] = OrderedDict()
        self._lock = RLock()
        self._changed = Condition(self._lock)
        self._generation = 0
        self._hits = 0
        self._misses = 0
        self._expirations = 0

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def publish(self, key: str, entry: HotStateEntry[object]) -> bool:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be nonempty")
        if not isinstance(entry, HotStateEntry):
            raise TypeError("entry must be HotStateEntry")
        key = key.strip()
        with self._changed:
            current = self._entries.get(key)
            if current is not None and entry.revision < current.revision:
                return False
            if current == entry:
                return False
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
            self._generation += 1
            self._changed.notify_all()
            return True

    def get(
        self, key: str, *, now: datetime | None = None,
    ) -> HotStateEntry[object] | None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("key must be nonempty")
        now = now or datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        with self._changed:
            entry = self._entries.get(key.strip())
            if entry is None:
                self._misses += 1
                record_cache(hit=False)
                return None
            if entry.expires_at <= now:
                del self._entries[key.strip()]
                self._misses += 1
                self._expirations += 1
                self._generation += 1
                self._changed.notify_all()
                record_cache(hit=False)
                return None
            self._hits += 1
            record_cache(hit=True)
            self._entries.move_to_end(key.strip())
            return entry

    def invalidate(self, key: str) -> bool:
        with self._changed:
            if self._entries.pop(key, None) is None:
                return False
            self._generation += 1
            self._changed.notify_all()
            return True

    def wait_for_change(self, generation: int, *, timeout: float | None = None) -> int:
        """Wait for an internal publication; external sources still need polling."""
        if type(generation) is not int or generation < 0:
            raise ValueError("generation must be a nonnegative integer")
        with self._changed:
            self._changed.wait_for(
                lambda: self._generation != generation,
                timeout=timeout,
            )
            return self._generation

    def stats(self) -> HotStateStats:
        with self._lock:
            return HotStateStats(
                hits=self._hits,
                misses=self._misses,
                expirations=self._expirations,
                entries=len(self._entries),
            )
