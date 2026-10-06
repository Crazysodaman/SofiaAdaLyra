"""Application-shared event-driven NEURO runtime."""
from __future__ import annotations

from datetime import datetime
import hashlib
import re
from threading import RLock

from sofia.cognition.matrix import (
    MatrixConfidence,
    MatrixRelevance,
    TurnMatrix,
)

from .homeostasis import HomeostasisController
from .model import NeuralSignal, NeuroStateSnapshot
from .salience import SalienceNetwork


_CONFIDENCE = {
    MatrixConfidence.LOW: 0.55,
    MatrixConfidence.MEDIUM: 0.75,
    MatrixConfidence.HIGH: 0.95,
}


class NeuroRuntime:
    """Tiny non-LLM attention layer shared by Sofía's application surfaces.

    It cannot execute tools, grant authority, write memories, infer consent, or
    create factual evidence. It only ranks already-observed host signals.
    """

    def __init__(
        self,
        *,
        network: SalienceNetwork | None = None,
        homeostasis: HomeostasisController | None = None,
    ) -> None:
        self._network = network or SalienceNetwork()
        self._homeostasis = homeostasis or HomeostasisController()
        self._recent_turn_fingerprints: list[str] = []
        self._last_snapshot: NeuroStateSnapshot | None = None
        self._lock = RLock()

    @property
    def last_snapshot(self) -> NeuroStateSnapshot | None:
        with self._lock:
            return self._last_snapshot

    @staticmethod
    def _fingerprint(content: str) -> str:
        normalized = " ".join(
            re.findall(r"[a-z0-9]+", content.casefold())
        )
        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    def _turn_novelty(self, content: str) -> float:
        fingerprint = self._fingerprint(content)
        novelty = (
            0.25
            if fingerprint in self._recent_turn_fingerprints
            else 0.85
        )
        self._recent_turn_fingerprints.append(fingerprint)
        del self._recent_turn_fingerprints[:-8]
        return novelty

    def observe_signal(self, signal: NeuralSignal) -> NeuroStateSnapshot:
        """Ingest one externally constructed host signal and return new state."""
        if not isinstance(signal, NeuralSignal):
            raise TypeError("signal must be NeuralSignal")
        with self._lock:
            self._network.ingest(signal)
            return self._snapshot_unlocked(now=signal.observed_at)

    def observe_turn(
        self,
        *,
        content: str,
        created_at: datetime,
        channel: str,
        turn: TurnMatrix | None,
    ) -> NeuroStateSnapshot:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be nonempty")
        if not isinstance(channel, str) or not channel.strip():
            raise ValueError("channel must be nonempty")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if turn is not None and not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix or None")

        with self._lock:
            novelty = self._turn_novelty(content)
            confidence = (
                0.65 if turn is None else _CONFIDENCE[turn.confidence]
            )

            self._network.ingest(
                NeuralSignal(
                    source=f"conversation:{channel.strip().casefold()}",
                    kind="foreground",
                    value=1.0,
                    confidence=confidence,
                    novelty=novelty,
                    urgency=0.82,
                    observed_at=created_at,
                    ttl_seconds=180.0,
                )
            )

            if turn is not None:
                for contribution in turn.domains:
                    if contribution.relevance is MatrixRelevance.NONE:
                        continue
                    relevance = float(contribution.relevance.value) / float(
                        MatrixRelevance.REQUIRED.value
                    )
                    self._network.ingest(
                        NeuralSignal(
                            source=f"domain:{contribution.domain.value}",
                            kind="matrix-domain",
                            value=relevance,
                            confidence=confidence,
                            novelty=novelty,
                            urgency=min(
                                1.0,
                                0.52 + 0.16 * contribution.relevance.value,
                            ),
                            observed_at=created_at,
                            ttl_seconds=240.0,
                        )
                    )

            return self._snapshot_unlocked(now=created_at)

    def snapshot(self, *, now: datetime) -> NeuroStateSnapshot:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        with self._lock:
            return self._snapshot_unlocked(now=now)

    def _snapshot_unlocked(self, *, now: datetime) -> NeuroStateSnapshot:
        activations = self._network.activations(now=now)
        homeostasis = self._homeostasis.update(activations)
        snapshot = NeuroStateSnapshot(
            generated_at=now,
            focus=(activations[0] if activations else None),
            secondary=activations[1:4],
            homeostasis=homeostasis,
            active_signal_count=len(activations),
        )
        self._last_snapshot = snapshot
        return snapshot
