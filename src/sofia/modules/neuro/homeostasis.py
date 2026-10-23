"""Slow bounded homeostatic state derived from current activations."""
from __future__ import annotations

from .model import HomeostaticState, NeuralActivation


class HomeostasisController:
    """Track low-cost load variables without inventing subjective state."""

    def __init__(self, *, smoothing: float = 0.25) -> None:
        if (
            isinstance(smoothing, bool)
            or not isinstance(smoothing, (int, float))
            or not 0.0 < float(smoothing) <= 1.0
        ):
            raise ValueError("smoothing must be in (0, 1]")
        self._smoothing = float(smoothing)
        self._state = HomeostaticState()

    @property
    def state(self) -> HomeostaticState:
        return self._state

    def update(
        self,
        activations: tuple[NeuralActivation, ...],
    ) -> HomeostaticState:
        if not isinstance(activations, tuple) or any(
            not isinstance(item, NeuralActivation)
            for item in activations
        ):
            raise TypeError("activations must contain NeuralActivation values")

        if not activations:
            target_load = 0.0
            target_novelty = 0.0
            target_competition = 0.0
        else:
            top = activations[0].score
            secondary_mass = sum(
                item.score for item in activations[1:5]
            )
            target_load = min(1.0, top + 0.20 * secondary_mass)
            target_novelty = min(
                1.0,
                sum(item.novelty for item in activations[:5])
                / max(1, min(5, len(activations))),
            )
            runner_up = (
                activations[1].score
                if len(activations) > 1
                else 0.0
            )
            # Competition rises when multiple strong candidates are close.
            target_competition = min(
                1.0,
                runner_up * (1.0 - max(0.0, top - runner_up)),
            )

        def smooth(previous: float, target: float) -> float:
            return max(
                0.0,
                min(
                    1.0,
                    previous
                    + self._smoothing * (target - previous),
                ),
            )

        self._state = HomeostaticState(
            cognitive_load=smooth(
                self._state.cognitive_load,
                target_load,
            ),
            novelty_load=smooth(
                self._state.novelty_load,
                target_novelty,
            ),
            competition_pressure=smooth(
                self._state.competition_pressure,
                target_competition,
            ),
        )
        return self._state
