from dataclasses import dataclass, field

from sofia.machine.comparison import (
    ObservationChange,
    ObservationComparison,
    compare_machine_observations,
)
from sofia.machine.observation import MachineObservation


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