from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from sofia.system.model import (
    SystemCapabilityName,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
)


def _validate_machine_id(machine_id: str) -> None:
    if not isinstance(machine_id, str):
        raise TypeError("machine_id must be a string")

    if not machine_id.strip():
        raise ValueError("machine_id must not be empty")


def _freeze_evidence(value: Any) -> Any:
    """
    Recursively detach and freeze evidence before it enters system knowledge.

    System capability evidence is observational data. Once recorded, the
    knowledge layer must own its snapshot and callers must not be able to
    mutate that snapshot through aliases to the original input.
    """
    if isinstance(value, Mapping):
        frozen_items = {
            key: _freeze_evidence(item)
            for key, item in value.items()
        }
        return MappingProxyType(frozen_items)

    if isinstance(value, tuple):
        return tuple(_freeze_evidence(item) for item in value)

    if isinstance(value, list):
        return tuple(_freeze_evidence(item) for item in value)

    if isinstance(value, set):
        return frozenset(_freeze_evidence(item) for item in value)

    return deepcopy(value)


def _capability_order(
    capability: SystemCapabilityName,
) -> int:
    """
    Return the canonical declaration order of a capability.

    Canonical ordering is deliberately independent of the capability's
    string value.
    """
    return tuple(SystemCapabilityName).index(capability)


@dataclass(frozen=True)
class SystemCapabilityKnowledgeRecord:
    """
    Current machine-scoped knowledge for one system capability.

    A record is an immutable snapshot. Successful evidence is recursively
    frozen so neither the original result nor a nested mutable object can
    mutate the recorded observation after ingestion.
    """

    machine_id: str
    capability: SystemCapabilityName
    kind: SystemCapabilityResultKind
    evidence: Mapping[str, Any] | None
    observed_at: datetime | None
    backend_name: str | None
    error: str | None = None

    def __post_init__(self) -> None:
        _validate_machine_id(self.machine_id)

        if not isinstance(self.capability, SystemCapabilityName):
            raise TypeError(
                "capability must be a SystemCapabilityName"
            )

        if not isinstance(self.kind, SystemCapabilityResultKind):
            raise TypeError(
                "kind must be a SystemCapabilityResultKind"
            )

        if self.backend_name is not None:
            if not isinstance(self.backend_name, str):
                raise TypeError(
                    "backend_name must be a string or None"
                )

            if not self.backend_name.strip():
                raise ValueError(
                    "backend_name must not be empty"
                )

        if self.evidence is not None:
            if not isinstance(self.evidence, Mapping):
                raise TypeError("evidence must be a mapping")

            frozen = _freeze_evidence(self.evidence)

            if not isinstance(frozen, Mapping):
                raise TypeError("evidence must be a mapping")

            object.__setattr__(self, "evidence", frozen)

        if (
            self.kind is SystemCapabilityResultKind.SUCCESS
            and self.evidence is None
        ):
            raise ValueError(
                "successful knowledge records require evidence"
            )

        if (
            self.kind is not SystemCapabilityResultKind.SUCCESS
            and self.evidence is not None
        ):
            raise ValueError(
                "non-success knowledge records must not contain evidence"
            )


@dataclass(frozen=True)
class SystemCapabilityKnowledgeUpdate:
    """
    Result of recording one capability observation.

    `changed` describes whether the newly recorded snapshot differs from the
    previously known snapshot for the same machine and capability.
    """

    current: SystemCapabilityKnowledgeRecord
    previous: SystemCapabilityKnowledgeRecord | None
    changed: bool


class SystemCapabilityKnowledge:
    """
    Current operational knowledge derived from system capability inspection.

    This layer stores structured observational evidence. It does not:
    - authorize capabilities,
    - execute capabilities,
    - interpret natural-language requests,
    - modify machine identity,
    - modify stable machine inventory,
    - or grant authority.

    Knowledge is scoped by machine identity and capability.
    """

    def __init__(self) -> None:
        self._records: dict[
            str,
            dict[
                SystemCapabilityName,
                SystemCapabilityKnowledgeRecord,
            ],
        ] = {}

    def record(
        self,
        machine_id: str,
        result: SystemCapabilityResult,
    ) -> SystemCapabilityKnowledgeUpdate:
        _validate_machine_id(machine_id)

        if not isinstance(result, SystemCapabilityResult):
            raise TypeError(
                "result must be a SystemCapabilityResult"
            )

        record = SystemCapabilityKnowledgeRecord(
            machine_id=machine_id,
            capability=result.capability,
            kind=result.kind,
            evidence=result.evidence,
            observed_at=result.observed_at,
            backend_name=result.backend_name,
            error=result.error,
        )

        machine_records = self._records.setdefault(machine_id, {})
        previous = machine_records.get(result.capability)

        machine_records[result.capability] = record

        return SystemCapabilityKnowledgeUpdate(
            current=record,
            previous=previous,
            changed=previous != record,
        )

    def record_all(
        self,
        machine_id: str,
        results: Sequence[SystemCapabilityResult],
    ) -> tuple[SystemCapabilityKnowledgeUpdate, ...]:
        _validate_machine_id(machine_id)

        if not isinstance(results, Sequence):
            raise TypeError(
                "results must be a sequence of SystemCapabilityResult"
            )

        updates: list[SystemCapabilityKnowledgeUpdate] = []

        for result in results:
            updates.append(self.record(machine_id, result))

        return tuple(updates)

    def get(
        self,
        machine_id: str,
        capability: SystemCapabilityName,
    ) -> SystemCapabilityKnowledgeRecord | None:
        _validate_machine_id(machine_id)

        if not isinstance(capability, SystemCapabilityName):
            raise TypeError(
                "capability must be a SystemCapabilityName"
            )

        return self._records.get(machine_id, {}).get(capability)

    def all_for_machine(
        self,
        machine_id: str,
    ) -> tuple[SystemCapabilityKnowledgeRecord, ...]:
        _validate_machine_id(machine_id)

        records = self._records.get(machine_id, {})

        return tuple(
            records[capability]
            for capability in sorted(
                records,
                key=_capability_order,
            )
        )

    def machine_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))

    def capabilities_for_machine(
        self,
        machine_id: str,
    ) -> tuple[SystemCapabilityName, ...]:
        _validate_machine_id(machine_id)

        return tuple(
            sorted(
                self._records.get(machine_id, {}),
                key=_capability_order,
            )
        )

    def clear_machine(self, machine_id: str) -> None:
        _validate_machine_id(machine_id)

        self._records.pop(machine_id, None)