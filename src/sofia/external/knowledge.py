from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sofia.external.model import (
    ExternalObservationState,
    ExternalSystem,
    ExternalSystemObservation,
)


def _validate_system_id(system_id: str) -> None:
    if not isinstance(system_id, str):
        raise TypeError("system_id must be a string.")

    if not system_id.strip():
        raise ValueError("system_id must not be empty.")


@dataclass(frozen=True)
class ExternalSystemKnowledgeRecord:
    """
    Immutable current knowledge about one external system observation.

    Stable external-system identity is retained separately from the
    dynamic observation. The observation itself is already immutable
    and recursively freezes its evidence at construction time.
    """

    system: ExternalSystem
    observation: ExternalSystemObservation

    def __post_init__(self) -> None:
        if not isinstance(self.system, ExternalSystem):
            raise TypeError(
                "system must be an ExternalSystem."
            )

        if not isinstance(
            self.observation,
            ExternalSystemObservation,
        ):
            raise TypeError(
                "observation must be an ExternalSystemObservation."
            )

        if self.observation.system != self.system:
            raise ValueError(
                "observation system must match the "
                "registered external system."
            )

    @property
    def system_id(self) -> str:
        return self.system.system_id

    @property
    def observed_at(self) -> datetime:
        return self.observation.observed_at

    @property
    def state(self) -> ExternalObservationState:
        return self.observation.state

    @property
    def evidence(self) -> Mapping[str, Any] | None:
        return self.observation.evidence


@dataclass(frozen=True)
class ExternalSystemKnowledgeUpdate:
    """
    Result of recording an external-system observation.

    `previous` is the prior current observation for the same system.
    `changed` reports whether the current snapshot changed.
    """

    current: ExternalSystemKnowledgeRecord
    previous: ExternalSystemKnowledgeRecord | None
    changed: bool


class ExternalSystemKnowledge:
    """
    Knowledge store for known external systems and their observations.

    Stable external-system identity is registered independently from
    dynamic observations.

    This class does not:
    - authorize actions,
    - execute actions,
    - authenticate,
    - own credentials,
    - interpret natural language,
    - register capabilities,
    - or mutate ExternalSystem identity.
    """

    def __init__(self) -> None:
        self._systems: dict[str, ExternalSystem] = {}
        self._current: dict[
            str,
            ExternalSystemKnowledgeRecord,
        ] = {}
        self._history: dict[
            str,
            list[ExternalSystemKnowledgeRecord],
        ] = {}

    def register(
        self,
        system: ExternalSystem,
    ) -> ExternalSystem:
        if not isinstance(system, ExternalSystem):
            raise TypeError(
                "system must be an ExternalSystem."
            )

        existing = self._systems.get(system.system_id)

        if existing is not None:
            if existing != system:
                raise ValueError(
                    "An external system with this system_id is "
                    "already registered with different identity data."
                )

            return existing

        self._systems[system.system_id] = system

        return system

    def get_system(
        self,
        system_id: str,
    ) -> ExternalSystem | None:
        _validate_system_id(system_id)

        return self._systems.get(system_id)

    def system_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._systems))

    def systems(self) -> tuple[ExternalSystem, ...]:
        return tuple(
            self._systems[system_id]
            for system_id in sorted(self._systems)
        )

    def record(
        self,
        observation: ExternalSystemObservation,
    ) -> ExternalSystemKnowledgeUpdate:
        if not isinstance(
            observation,
            ExternalSystemObservation,
        ):
            raise TypeError(
                "observation must be an ExternalSystemObservation."
            )

        system_id = observation.system_id
        system = self._systems.get(system_id)

        if system is None:
            raise KeyError(
                f"External system '{system_id}' is not known."
            )

        if observation.system != system:
            raise ValueError(
                "observation system does not match the "
                "registered external system."
            )

        record = ExternalSystemKnowledgeRecord(
            system=system,
            observation=observation,
        )

        previous = self._current.get(system_id)

        self._current[system_id] = record
        self._history.setdefault(system_id, []).append(record)

        return ExternalSystemKnowledgeUpdate(
            current=record,
            previous=previous,
            changed=previous != record,
        )

    def current(
        self,
        system_id: str,
    ) -> ExternalSystemKnowledgeRecord | None:
        _validate_system_id(system_id)

        return self._current.get(system_id)

    def history(
        self,
        system_id: str,
    ) -> tuple[ExternalSystemKnowledgeRecord, ...]:
        _validate_system_id(system_id)

        return tuple(
            self._history.get(system_id, ())
        )

    def mark_stale(
        self,
        system_id: str,
    ) -> ExternalSystemKnowledgeUpdate | None:
        current = self.current(system_id)

        if current is None:
            return None

        observation = current.observation

        stale = ExternalSystemObservation(
            system=observation.system,
            observed_at=observation.observed_at,
            state=ExternalObservationState.STALE,
            evidence=None,
            source_name=observation.source_name,
        )

        return self.record(stale)

    def invalidate(
        self,
        system_id: str,
    ) -> ExternalSystemKnowledgeUpdate | None:
        current = self.current(system_id)

        if current is None:
            return None

        observation = current.observation

        unknown = ExternalSystemObservation(
            system=observation.system,
            observed_at=observation.observed_at,
            state=ExternalObservationState.UNKNOWN,
            evidence=None,
            source_name=observation.source_name,
        )

        return self.record(unknown)

    def record_contradiction(
        self,
        observation: ExternalSystemObservation,
    ) -> ExternalSystemKnowledgeRecord:
        if not isinstance(
            observation,
            ExternalSystemObservation,
        ):
            raise TypeError(
                "observation must be an ExternalSystemObservation."
            )

        if observation.state is not ExternalObservationState.CONTRADICTED:
            raise ValueError(
                "Contradictory evidence must have "
                "CONTRADICTED observation state."
            )

        system_id = observation.system_id
        system = self._systems.get(system_id)

        if system is None:
            raise KeyError(
                f"External system '{system_id}' is not known."
            )

        if observation.system != system:
            raise ValueError(
                "observation system does not match the "
                "registered external system."
            )

        current = self._current.get(system_id)

        if current is None:
            raise ValueError(
                "Cannot record contradictory evidence for an "
                "external system without current knowledge."
            )

        if observation == current.observation:
            raise ValueError(
                "Contradictory evidence must differ from "
                "the current observation."
            )

        record = ExternalSystemKnowledgeRecord(
            system=system,
            observation=observation,
        )

        self._history.setdefault(system_id, []).append(record)

        return record

    def clear(
        self,
        system_id: str,
    ) -> None:
        _validate_system_id(system_id)

        self._current.pop(system_id, None)
        self._history.pop(system_id, None)