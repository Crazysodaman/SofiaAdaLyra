"""Optional bounded circuit-competition prototype."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompetitionResult:
    activations: tuple[tuple[str, float], ...]
    winner: str | None
    iterations: int


class CircuitCompetition:
    ALGORITHM_VERSION = "connectome-competition-v0.1"

    def __init__(
        self, *, recurrent_excitation: float = 0.18,
        lateral_inhibition: float = 0.22, decay: float = 0.12,
    ) -> None:
        for value in (recurrent_excitation, lateral_inhibition, decay):
            if not 0 <= value <= 0.5:
                raise ValueError("competition parameters must be in 0..0.5")
        self.recurrent_excitation = recurrent_excitation
        self.lateral_inhibition = lateral_inhibition
        self.decay = decay

    def run(self, inputs: dict[str, float], *, iterations: int = 6) -> CompetitionResult:
        if not 1 <= iterations <= 32 or not inputs or len(inputs) > 64:
            raise ValueError("competition requires 1..64 inputs and 1..32 iterations")
        state = {}
        for key, value in inputs.items():
            if not isinstance(key, str) or not key or not 0 <= value <= 1:
                raise ValueError("competition inputs require bounded IDs and values")
            state[key] = float(value)
        for _ in range(iterations):
            previous = dict(state)
            total = sum(previous.values())
            for key, drive in inputs.items():
                inhibition = self.lateral_inhibition * max(0.0, total - previous[key])
                state[key] = max(0.0, min(1.0,
                    float(drive)
                    + self.recurrent_excitation * previous[key]
                    - inhibition
                    - self.decay * previous[key]
                ))
        ordered = tuple(sorted(state.items(), key=lambda item: (-item[1], item[0])))
        return CompetitionResult(ordered, ordered[0][0] if ordered else None, iterations)
