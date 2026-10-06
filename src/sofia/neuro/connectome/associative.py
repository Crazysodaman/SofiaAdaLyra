"""Bounded mushroom-body-style association prototype with MEM gate intact."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


_ID = re.compile(r"^[A-Za-z0-9_.:/-]{1,120}$")


@dataclass(frozen=True, slots=True)
class AssociationCandidate:
    memory_id: str
    activation: float
    reinforcement_refs: tuple[str, ...]


class SparseAssociativeMemory:
    ALGORITHM_VERSION = "mushroom-association-v0.1"

    def __init__(self, *, width: int = 256, active_units: int = 12) -> None:
        if not 32 <= width <= 4096 or not 2 <= active_units <= min(64, width):
            raise ValueError("invalid sparse expansion bounds")
        self.width = width
        self.active_units = active_units
        self._weights: dict[tuple[int, str], float] = {}
        self._provenance: dict[str, list[str]] = {}

    def _expand(self, features: tuple[str, ...]) -> tuple[int, ...]:
        if not features or len(features) > 64 or any(_ID.fullmatch(x) is None for x in features):
            raise ValueError("features must be 1..64 machine-safe eligible IDs")
        ranked = sorted({
            int.from_bytes(sha256(feature.encode()).digest()[:8], "big") % self.width
            for feature in features
        })
        return tuple(ranked[:self.active_units])

    def reinforce(
        self, *, features: tuple[str, ...], memory_id: str,
        reinforcement_ref: str, amount: float,
    ) -> None:
        if _ID.fullmatch(memory_id) is None or _ID.fullmatch(reinforcement_ref) is None:
            raise ValueError("memory and reinforcement IDs must be machine-safe")
        if not -0.1 <= amount <= 0.1:
            raise ValueError("bounded reinforcement amount must be in -0.1..0.1")
        for unit in self._expand(features):
            key = (unit, memory_id)
            self._weights[key] = max(-1.0, min(1.0, self._weights.get(key, 0.0) + amount))
        refs = self._provenance.setdefault(memory_id, [])
        if reinforcement_ref not in refs:
            refs.append(reinforcement_ref)
            del refs[:-32]

    def candidates(self, *, features: tuple[str, ...], eligible) -> tuple[AssociationCandidate, ...]:
        if not callable(eligible):
            raise TypeError("MEM eligibility callback is required")
        units = self._expand(features)
        memory_ids = {memory for unit, memory in self._weights if unit in units}
        result = []
        for memory_id in memory_ids:
            if not eligible(memory_id):
                continue
            score = sum(max(0.0, self._weights.get((unit, memory_id), 0.0)) for unit in units)
            score = min(1.0, score / max(1, len(units)))
            if score > 0:
                result.append(AssociationCandidate(
                    memory_id, score, tuple(self._provenance.get(memory_id, ())),
                ))
        return tuple(sorted(result, key=lambda item: (-item.activation, item.memory_id)))[:16]

    def decay(self, rate: float = 0.01) -> None:
        if not 0 <= rate <= 0.1:
            raise ValueError("decay rate must be in 0..0.1")
        self._weights = {
            key: value * (1.0 - rate)
            for key, value in self._weights.items()
            if abs(value * (1.0 - rate)) >= 0.001
        }

    def export(self) -> dict:
        return {
            "algorithm": self.ALGORITHM_VERSION,
            "width": self.width,
            "active_units": self.active_units,
            "weights": [
                {"unit": unit, "memory_id": memory, "weight": weight,
                 "reinforcement_refs": tuple(self._provenance.get(memory, ()))}
                for (unit, memory), weight in sorted(self._weights.items())
            ],
        }

    def reset(self) -> None:
        self._weights.clear()
        self._provenance.clear()
