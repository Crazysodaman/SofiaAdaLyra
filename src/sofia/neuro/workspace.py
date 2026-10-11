"""Bounded, transient attention broadcast for the one production NEURO.

This is a non-authoritative projection of existing eligible activations.
No new evidence, memory, emotional truth, tools or execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from threading import RLock

from .model import NeuroStateSnapshot, NeuralActivation


@dataclass(frozen=True, slots=True)
class WorkspaceBroadcast:
    generation: str
    published_at: datetime
    expires_at: datetime
    items: tuple[NeuralActivation, ...]
    selection_method: str

    def __post_init__(self):
        if not 0 <= len(self.items) <= 3:
            raise ValueError("workspace holds no more than three items")
        if (
            self.published_at.tzinfo is None or self.expires_at.tzinfo is None
            or self.expires_at <= self.published_at
            or self.expires_at-self.published_at > timedelta(seconds=120)
        ):
            raise ValueError("bounded timezone-aware workspace lease required")


class NeuroSharedWorkspace:
    """One bounded broadcast inside the existing NeuroRuntime lifetime."""

    CONSUMERS = frozenset({"conversation", "personality", "run", "act"})

    def __init__(self, *, max_items=3, ttl_seconds=90):
        if type(max_items) is not int or not 1 <= max_items <= 3:
            raise ValueError("workspace width must be 1..3")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 120:
            raise ValueError("workspace lifetime must be 1..120 seconds")
        self._max_items = max_items
        self._ttl_seconds = ttl_seconds
        self._broadcast: WorkspaceBroadcast | None = None
        self._lock = RLock()

    def publish(self, snapshot: NeuroStateSnapshot) -> WorkspaceBroadcast:
        if not isinstance(snapshot, NeuroStateSnapshot):
            raise TypeError("only host-created NEURO snapshot may be broadcast")
        chosen = tuple(
            item for item in (snapshot.focus, *snapshot.secondary)
            if item is not None
        )[:self._max_items]
        serialized = json.dumps(
            [(item.key, round(item.score, 6)) for item in chosen],
            sort_keys=True, separators=(",", ":"),
        )
        generation = sha256((
            snapshot.generated_at.astimezone(timezone.utc).isoformat()
            + ":" + snapshot.selection_method + ":" + serialized
        ).encode("utf-8")).hexdigest()[:24]
        published = WorkspaceBroadcast(
            generation=generation,
            published_at=snapshot.generated_at,
            expires_at=snapshot.generated_at + timedelta(seconds=self._ttl_seconds),
            items=chosen,
            selection_method=snapshot.selection_method,
        )
        with self._lock:
            self._broadcast = published
        return published

    def read(self, *, consumer: str, at: datetime) -> WorkspaceBroadcast | None:
        if consumer not in self.CONSUMERS:
            raise PermissionError("only real downstream workspace consumers allowed")
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("timezone-aware broadcast read time required")
        with self._lock:
            candidate = self._broadcast
        if (
            candidate is None
            or not candidate.published_at <= at < candidate.expires_at
        ):
            return None
        return candidate

    def clear(self) -> None:
        """Reset projection without changing underlying trusted signals."""
        with self._lock:
            self._broadcast = None
