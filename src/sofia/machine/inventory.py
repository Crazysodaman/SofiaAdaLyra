from dataclasses import dataclass, field

from sofia.machine.comparison import (
    ObservationChange,
    ObservationComparison,
    compare_machine_observations,
)
from sofia.machine.observation import (
    MachineObservation,
    ObservationState,
)


@dataclass
class MachineInventory:
    _current: dict[str, MachineObservation] = field(
        default_factory=dict,
        repr=False,
    )
    _history: dict[str, list[MachineObservation]] = field(
        default_factory=dict,
        repr=False,
    )

    def record(
        self,
        observation: MachineObservation,
    ) -> ObservationComparison | None:
        if not isinstance(observation, MachineObservation):
            raise TypeError(
                "observation must be a MachineObservation."
            )

        machine_id = observation.machine_id
        previous = self._current.get(machine_id)

        if previous is None:
            self._current[machine_id] = observation
            self._history.setdefault(machine_id, []).append(
                observation
            )
            return None

        comparison = compare_machine_observations(
            previous,
            observation,
        )

        if comparison.change is ObservationChange.NO_CHANGE:
            self._current[machine_id] = previous.reverified(
                observation.verified_at
            )
            return comparison

        self._current[machine_id] = observation
        self._history.setdefault(machine_id, []).append(
            observation
        )

        return comparison

    def mark_stale(
        self,
        machine_id: str,
    ) -> ObservationComparison | None:
        observation = self.get(machine_id)

        if observation is None:
            return None

        stale = observation.with_state(
            ObservationState.STALE
        )

        return self.record(stale)

    def invalidate(
        self,
        machine_id: str,
    ) -> ObservationComparison | None:
        observation = self.get(machine_id)

        if observation is None:
            return None

        unknown = observation.with_state(
            ObservationState.UNKNOWN
        )

        return self.record(unknown)

    def record_contradiction(
        self,
        observation: MachineObservation,
    ) -> ObservationComparison:
        if not isinstance(observation, MachineObservation):
            raise TypeError(
                "observation must be a MachineObservation."
            )

        machine_id = observation.machine_id
        current = self._current.get(machine_id)

        if current is None:
            raise ValueError(
                "Cannot record contradictory evidence for "
                "an unknown machine."
            )

        comparison = compare_machine_observations(
            current,
            observation,
        )

        if not (
            comparison.identity_changed
            or comparison.operating_system_changed
            or comparison.virtualization_changed
            or comparison.hardware_changed
        ):
            raise ValueError(
                "Contradictory evidence must differ from "
                "the current machine observation."
            )

        contradicted = observation.with_state(
            ObservationState.CONTRADICTED
        )

        contradiction_comparison = (
            compare_machine_observations(
                current,
                contradicted,
            )
        )

        self._history.setdefault(machine_id, []).append(
            contradicted
        )

        return contradiction_comparison

    def get(
        self,
        machine_id: str,
    ) -> MachineObservation | None:
        if not isinstance(machine_id, str):
            raise TypeError(
                "machine_id must be a string."
            )

        if not machine_id.strip():
            raise ValueError(
                "machine_id must not be empty."
            )

        return self._current.get(machine_id)

    def history(
        self,
        machine_id: str,
    ) -> tuple[MachineObservation, ...]:
        if not isinstance(machine_id, str):
            raise TypeError(
                "machine_id must be a string."
            )

        if not machine_id.strip():
            raise ValueError(
                "machine_id must not be empty."
            )

        return tuple(
            self._history.get(machine_id, ())
        )

    def machine_ids(self) -> tuple[str, ...]:
        return tuple(self._current.keys())

    def __len__(self) -> int:
        return len(self._current)