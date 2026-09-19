from __future__ import annotations

from dataclasses import dataclass

from sofia.machine.inventory import MachineInventory
from sofia.machine.observation import MachineObservation
from sofia.system.knowledge import (
    SystemCapabilityKnowledge,
    SystemCapabilityKnowledgeRecord,
)
from sofia.system.model import (
    SystemCapabilityName,
    SystemCapabilityResult,
)


@dataclass(frozen=True)
class SystemCapabilityMachineAssociation:
    """
    Immutable association between dynamic system capability knowledge
    and a known machine observation.

    The association does not copy or mutate machine inventory. It only
    establishes that the capability knowledge is scoped to a machine
    currently known by the inventory.
    """

    machine: MachineObservation
    system_capability_knowledge: SystemCapabilityKnowledge


class SystemCapabilityMachineKnowledge:
    """
    Coordinates machine-scoped system capability knowledge.

    Stable machine identity and hardware remain owned by MachineInventory.
    Dynamic process, system, network, service, and hardware inspection
    evidence remains owned by SystemCapabilityKnowledge.

    This class performs association only. It does not:
    - execute capabilities,
    - authorize capabilities,
    - modify MachineInventory,
    - modify MachineObservation,
    - modify MachineProfile,
    - interpret natural language,
    - or convert dynamic evidence into stable machine identity.
    """

    def __init__(
        self,
        machine_inventory: MachineInventory,
        system_capability_knowledge: SystemCapabilityKnowledge,
    ) -> None:
        if not isinstance(
            machine_inventory,
            MachineInventory,
        ):
            raise TypeError(
                "machine_inventory must be a MachineInventory."
            )

        if not isinstance(
            system_capability_knowledge,
            SystemCapabilityKnowledge,
        ):
            raise TypeError(
                "system_capability_knowledge must be "
                "a SystemCapabilityKnowledge."
            )

        self._machine_inventory = machine_inventory
        self._system_capability_knowledge = (
            system_capability_knowledge
        )

    @property
    def machine_inventory(self) -> MachineInventory:
        return self._machine_inventory

    @property
    def system_capability_knowledge(
        self,
    ) -> SystemCapabilityKnowledge:
        return self._system_capability_knowledge

    def associate(
        self,
        machine_id: str,
    ) -> SystemCapabilityMachineAssociation:
        self._validate_machine_id(machine_id)

        machine = self._machine_inventory.get(machine_id)

        if machine is None:
            raise KeyError(
                f"Machine '{machine_id}' is not known to "
                "MachineInventory."
            )

        return SystemCapabilityMachineAssociation(
            machine=machine,
            system_capability_knowledge=(
                self._system_capability_knowledge
            ),
        )

    def record(
        self,
        machine_id: str,
        result: SystemCapabilityResult,
    ):
        self._validate_machine_id(machine_id)

        if not isinstance(
            result,
            SystemCapabilityResult,
        ):
            raise TypeError(
                "result must be a SystemCapabilityResult."
            )

        self.associate(machine_id)

        return self._system_capability_knowledge.record(
            machine_id,
            result,
        )

    def record_all(
        self,
        machine_id: str,
        results: tuple[SystemCapabilityResult, ...],
    ):
        self._validate_machine_id(machine_id)

        if not isinstance(results, tuple):
            raise TypeError(
                "results must be a tuple of SystemCapabilityResult."
            )

        self.associate(machine_id)

        return self._system_capability_knowledge.record_all(
            machine_id,
            results,
        )

    def current(
        self,
        machine_id: str,
    ) -> tuple[SystemCapabilityKnowledgeRecord, ...]:
        association = self.associate(machine_id)

        return association.system_capability_knowledge.all_for_machine(
            machine_id
        )

    def current_capability(
        self,
        machine_id: str,
        capability: SystemCapabilityName,
    ) -> SystemCapabilityKnowledgeRecord | None:
        association = self.associate(machine_id)

        return association.system_capability_knowledge.get(
            machine_id,
            capability,
        )

    @staticmethod
    def _validate_machine_id(machine_id: str) -> None:
        if not isinstance(machine_id, str):
            raise TypeError(
                "machine_id must be a string."
            )

        if not machine_id.strip():
            raise ValueError(
                "machine_id must not be empty."
            )