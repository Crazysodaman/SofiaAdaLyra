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
from .model import (
    NeuralSignal,
    NeuroRoutingDecision,
    NeuroStateSnapshot,
    NeuroWakeMode,
)
from .salience import SalienceNetwork
from .store import NeuroObservabilityStore


_CONFIDENCE = {
    MatrixConfidence.LOW: 0.55,
    MatrixConfidence.MEDIUM: 0.75,
    MatrixConfidence.HIGH: 0.95,
}
_TURN_SIGNAL_KINDS = frozenset({"foreground", "matrix-domain"})


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
        observability: NeuroObservabilityStore | None = None,
    ) -> None:
        self._network = network or SalienceNetwork()
        self._homeostasis = homeostasis or HomeostasisController()
        if observability is not None and not isinstance(
            observability, NeuroObservabilityStore
        ):
            raise TypeError("observability must be NeuroObservabilityStore or None")
        self._observability = observability
        self._last_observability_error: str | None = None
        self._recent_turn_fingerprints: list[str] = []
        self._recent_signals: list[NeuralSignal] = []
        self._last_snapshot: NeuroStateSnapshot | None = None
        self._last_homeostasis_signature: tuple[
            tuple[str, float, float], ...
        ] = ()
        self._lock = RLock()

    @property
    def last_snapshot(self) -> NeuroStateSnapshot | None:
        with self._lock:
            return self._last_snapshot

    @property
    def recent_signals(self) -> tuple[NeuralSignal, ...]:
        """Return bounded metadata-only input history for observability."""
        with self._lock:
            return tuple(self._recent_signals)

    @property
    def last_observability_error(self) -> str | None:
        with self._lock:
            return self._last_observability_error

    def _record_unlocked(
        self,
        snapshot: NeuroStateSnapshot,
        *,
        signals: tuple[NeuralSignal, ...] = (),
        routing: NeuroRoutingDecision | None = None,
    ) -> None:
        store = self._observability
        if store is None:
            return
        try:
            store.record(snapshot=snapshot, signals=signals, routing=routing)
            self._last_observability_error = None
        except Exception as exc:
            # Diagnostics must never take down conversation or action control.
            self._last_observability_error = type(exc).__name__

    @staticmethod
    def _fingerprint(content: str) -> str:
        normalized = " ".join(
            "".join(
                character if character.isalnum() else " "
                for character in content.casefold()
            ).split()
        )
        if not normalized:
            # Emoji/punctuation-only turns still have distinct novelty without
            # retaining their raw text.
            normalized = content.strip().casefold()
        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _channel_source(channel: str) -> str:
        raw = channel.strip().casefold()
        safe = re.sub(r"[^a-z0-9_.:/-]+", "-", raw).strip("-")
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        if not safe:
            safe = f"channel-{digest}"
        elif len(safe) > 90:
            safe = f"{safe[:77]}-{digest}"
        return f"conversation:{safe}"

    def _effective_now_unlocked(self, candidate: datetime) -> datetime:
        previous = self._last_snapshot
        if previous is not None and candidate < previous.generated_at:
            return previous.generated_at
        return candidate

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
        if signal.kind in _TURN_SIGNAL_KINDS:
            raise ValueError(
                "foreground and matrix-domain signals are reserved for observe_turn"
            )
        with self._lock:
            now = self._effective_now_unlocked(signal.observed_at)
            accepted = self._network.ingest(signal, now=now)
            if accepted:
                self._remember_signals_unlocked((signal,))
            snapshot = self._snapshot_unlocked(now=now, stimulus=accepted)
            self._record_unlocked(
                snapshot,
                signals=(signal,) if accepted else (),
            )
            return snapshot

    def replace_signals(
        self,
        *,
        kinds: frozenset[str],
        signals: tuple[NeuralSignal, ...],
        now: datetime,
    ) -> NeuroStateSnapshot:
        """Atomically replace current-state inputs owned by subsystem adapters."""
        if not isinstance(kinds, frozenset) or not kinds:
            raise TypeError("kinds must be a nonempty frozenset")
        if kinds & _TURN_SIGNAL_KINDS:
            raise ValueError("turn signal kinds are owned by observe_turn")
        if not isinstance(signals, tuple) or any(
            not isinstance(item, NeuralSignal) for item in signals
        ):
            raise TypeError("signals must be a tuple of NeuralSignal values")
        if any(item.kind not in kinds for item in signals):
            raise ValueError("replacement signals must belong to the supplied kinds")
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        with self._lock:
            effective = self._effective_now_unlocked(now)
            self._network.discard_kinds(kinds)
            accepted: list[NeuralSignal] = []
            for signal in signals:
                if self._network.ingest(signal, now=effective):
                    accepted.append(signal)
            self._remember_signals_unlocked(tuple(accepted))
            snapshot = self._snapshot_unlocked(
                now=effective,
                stimulus=bool(accepted),
            )
            self._record_unlocked(snapshot, signals=tuple(accepted))
            return snapshot

    def _remember_signals_unlocked(
        self,
        signals: tuple[NeuralSignal, ...],
    ) -> None:
        self._recent_signals.extend(signals)
        del self._recent_signals[:-32]

    def routing_decision(
        self,
        *,
        existing_hint: str | None = None,
    ) -> NeuroRoutingDecision:
        """Choose a compute tier without weakening Matrix high-stakes routing."""
        if existing_hint is not None:
            try:
                mode = NeuroWakeMode(existing_hint)
            except ValueError as exc:
                raise ValueError("unknown existing cognitive route") from exc
            decision = NeuroRoutingDecision(
                mode,
                "Matrix or explicit routing decision retained",
            )
            with self._lock:
                if self._last_snapshot is not None:
                    self._record_unlocked(self._last_snapshot, routing=decision)
            return decision
        with self._lock:
            snapshot = self._last_snapshot
        if snapshot is None or snapshot.focus is None:
            decision = NeuroRoutingDecision(
                NeuroWakeMode.FAST,
                "no competing neural activation",
            )
            return decision
        focus = snapshot.focus
        candidates = (focus, *snapshot.secondary)
        high_priority = next((
            item for item in candidates
            if item.kind in {"ops", "fleet", "run", "goal"}
            and item.score >= 0.72
        ), None)
        if high_priority is not None:
            decision = NeuroRoutingDecision(
                NeuroWakeMode.DEEP,
                f"high {high_priority.kind} salience",
            )
        elif not any(
            item.kind in {"emotion", "memory", "habit", "relationship"}
            and item.score >= 0.62
            for item in candidates
        ):
            decision = NeuroRoutingDecision(
                NeuroWakeMode.FAST,
                "no high-salience goal, fault, memory, or affective context",
            )
        else:
            decision = NeuroRoutingDecision(
                NeuroWakeMode.STANDARD,
                "moderate attention requires normal primary reasoning",
            )
        with self._lock:
            if self._last_snapshot is not None:
                self._record_unlocked(self._last_snapshot, routing=decision)
        return decision

    def background_priority(self, task_kind: str) -> float:
        """Return an advisory scheduler weight; readiness/authority still gate work."""
        if not isinstance(task_kind, str) or not task_kind.strip():
            raise ValueError("task_kind must be nonempty")
        with self._lock:
            snapshot = self._last_snapshot
        if snapshot is None:
            return 0.0
        task = task_kind.casefold()
        mappings = {
            "fleet": ("fleet", "ops"),
            "backup": ("ops", "run"),
            "habit": ("habit",),
            "expectation": ("habit", "relationship"),
            "reflection": ("emotion", "relationship", "goal"),
            "outreach": ("relationship", "emotion", "goal"),
            "avatar": ("avatar", "environment", "emotion"),
            "wardrobe": ("avatar", "environment", "emotion"),
            "neuro": ("run",),
            "goal": ("goal", "run"),
            "network": ("network", "fleet", "ops"),
            "web": ("network", "run"),
            "tunnel": ("network", "run"),
        }
        relevant = {
            kind
            for marker, kinds in mappings.items()
            if marker in task
            for kind in kinds
        }
        if not relevant:
            return 0.0
        return max(
            (
                item.score
                for item in (snapshot.focus, *snapshot.secondary)
                if item is not None and item.kind in relevant
            ),
            default=0.0,
        )

    def should_wake_for_reflection(self) -> bool:
        """Gate optional LLM reflection; deterministic/background tasks still run."""
        with self._lock:
            snapshot = self._last_snapshot
        if snapshot is None or snapshot.focus is None:
            return False
        return any(
            item.kind in {"emotion", "relationship", "goal", "memory"}
            and item.score >= 0.55
            for item in (snapshot.focus, *snapshot.secondary)
            if item is not None
        ) or snapshot.homeostasis.novelty_load >= 0.45

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
        if (
            not isinstance(created_at, datetime)
            or created_at.tzinfo is None
            or created_at.utcoffset() is None
        ):
            raise ValueError("created_at must be timezone-aware")
        if turn is not None and not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix or None")

        with self._lock:
            now = self._effective_now_unlocked(created_at)
            novelty = self._turn_novelty(content)
            confidence = (
                0.65 if turn is None else _CONFIDENCE[turn.confidence]
            )

            # Foreground and Matrix-domain activations describe exactly one
            # current turn. Retaining them lets a repeatedly reinforced old
            # topic outrank a new Matrix decision. Long-lived trusted external
            # signals (faults, goals, environment changes) remain untouched.
            self._network.discard_kinds(_TURN_SIGNAL_KINDS)

            foreground_signal = NeuralSignal(
                source=self._channel_source(channel),
                kind="foreground",
                value=1.0,
                confidence=confidence,
                novelty=novelty,
                urgency=0.82,
                observed_at=created_at,
                ttl_seconds=180.0,
            )
            self._network.ingest(foreground_signal, now=now)
            observed = [foreground_signal]

            if turn is not None:
                for contribution in turn.domains:
                    if contribution.relevance is MatrixRelevance.NONE:
                        continue
                    relevance = float(contribution.relevance.value) / float(
                        MatrixRelevance.REQUIRED.value
                    )
                    domain_signal = NeuralSignal(
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
                    self._network.ingest(
                        domain_signal,
                        now=now,
                    )
                    observed.append(domain_signal)

            remembered = tuple(observed)
            self._remember_signals_unlocked(remembered)
            snapshot = self._snapshot_unlocked(now=now, stimulus=True)
            self._record_unlocked(snapshot, signals=remembered)
            return snapshot

    def snapshot(self, *, now: datetime) -> NeuroStateSnapshot:
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        with self._lock:
            snapshot = self._snapshot_unlocked(
                now=self._effective_now_unlocked(now),
                stimulus=False,
            )
            self._record_unlocked(snapshot)
            return snapshot

    def _snapshot_unlocked(
        self,
        *,
        now: datetime,
        stimulus: bool,
    ) -> NeuroStateSnapshot:
        activations = self._network.activations(now=now)
        signature = tuple(
            (item.key, item.score, item.novelty)
            for item in activations
        )
        if stimulus or signature != self._last_homeostasis_signature:
            homeostasis = self._homeostasis.update(activations)
            self._last_homeostasis_signature = signature
        else:
            homeostasis = self._homeostasis.state
        snapshot = NeuroStateSnapshot(
            generated_at=now,
            focus=(activations[0] if activations else None),
            secondary=activations[1:4],
            homeostasis=homeostasis,
            active_signal_count=len(activations),
        )
        self._last_snapshot = snapshot
        return snapshot
