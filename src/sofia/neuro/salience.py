"""Event-driven salience accumulation and competition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from .model import NeuralActivation, NeuralSignal


@dataclass(slots=True)
class _Node:
    source: str
    kind: str
    score: float
    novelty: float
    updated_at: datetime
    expires_at: datetime


class SalienceNetwork:
    """Small deterministic salience network with decay and competition.

    No background loop is required. State decays lazily whenever a new signal
    arrives or a snapshot is requested.
    """

    def __init__(
        self,
        *,
        half_life_seconds: float = 120.0,
        max_nodes: int = 64,
    ) -> None:
        if (
            not isinstance(half_life_seconds, (int, float))
            or half_life_seconds <= 0
        ):
            raise ValueError("half_life_seconds must be positive")
        if type(max_nodes) is not int or not 1 <= max_nodes <= 1024:
            raise ValueError("max_nodes must be in 1..1024")
        self._half_life_seconds = float(half_life_seconds)
        self._max_nodes = max_nodes
        self._nodes: dict[str, _Node] = {}

    @staticmethod
    def signal_score(signal: NeuralSignal) -> float:
        """Convert one bounded signal into a deterministic activation score."""
        return min(
            1.0,
            (
                0.30 * float(signal.urgency)
                + 0.25 * float(signal.novelty)
                + 0.25 * float(signal.confidence)
                + 0.20 * float(signal.value)
            ),
        )

    def _decay(self, *, now: datetime) -> None:
        remove: list[str] = []
        for key, node in self._nodes.items():
            if now >= node.expires_at:
                remove.append(key)
                continue
            elapsed = max(
                0.0,
                (now - node.updated_at).total_seconds(),
            )
            if elapsed <= 0.0:
                continue
            factor = math.pow(
                0.5,
                elapsed / self._half_life_seconds,
            )
            node.score *= factor
            node.novelty *= factor
            node.updated_at = now
            if node.score < 0.01:
                remove.append(key)
        for key in remove:
            self._nodes.pop(key, None)

    def ingest(
        self,
        signal: NeuralSignal,
        *,
        now: datetime | None = None,
    ) -> None:
        if not isinstance(signal, NeuralSignal):
            raise TypeError("signal must be NeuralSignal")
        now = signal.observed_at if now is None else now
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        self._decay(now=now)
        if (now - signal.observed_at).total_seconds() > signal.ttl_seconds:
            return
        key = f"{signal.kind}:{signal.source}"
        existing = self._nodes.get(key)
        if (
            existing is not None
            and signal.observed_at < existing.updated_at
        ):
            # Distributed/event sources may arrive out of order. Old evidence
            # must not rewind a newer attention node.
            return
        score = self.signal_score(signal)
        if existing is not None:
            # Repeated stimulation strengthens a node without allowing a single
            # source to grow without bound.
            score = min(
                1.0,
                max(score, existing.score) + (0.20 * min(score, existing.score)),
            )
            novelty = max(float(signal.novelty), existing.novelty * 0.75)
        else:
            novelty = float(signal.novelty)
        self._nodes[key] = _Node(
            source=signal.source,
            kind=signal.kind,
            score=score,
            novelty=novelty,
            updated_at=now,
            expires_at=signal.observed_at + timedelta(
                seconds=float(signal.ttl_seconds)
            ),
        )
        if len(self._nodes) > self._max_nodes:
            weakest = min(
                self._nodes.items(),
                key=lambda item: (item[1].score, item[0]),
            )[0]
            self._nodes.pop(weakest, None)

    def activations(
        self,
        *,
        now: datetime,
    ) -> tuple[NeuralActivation, ...]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        self._decay(now=now)
        ranked = sorted(
            (
                NeuralActivation(
                    key=key,
                    source=node.source,
                    kind=node.kind,
                    score=max(0.0, min(1.0, node.score)),
                    novelty=max(0.0, min(1.0, node.novelty)),
                    updated_at=node.updated_at,
                )
                for key, node in self._nodes.items()
            ),
            key=lambda item: (-item.score, item.key),
        )
        return tuple(ranked)
