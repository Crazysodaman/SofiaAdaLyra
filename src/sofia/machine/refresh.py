from __future__ import annotations

from dataclasses import dataclass

from sofia.machine.discovery import (
    MachineDiscovery,
    MachineDiscoveryResult,
)
from sofia.machine.hardware import (
    HardwareDiscovery,
    HardwareDiscoveryResult,
)
from sofia.machine.inventory import MachineInventory
from sofia.machine.model import (
    MachineProfile,
    MachineVerification,
)
from sofia.machine.observation import (
    MachineObservation,
    ObservationProvenance,
    ObservationSource,
    ObservationState,
)


@dataclass(frozen=True)
class MachineRefreshResult:
    """
    Result of one machine-inventory refresh attempt.

    A refresh result describes what was actually observed. It never invents
    identity or hardware information to make a refresh appear successful.
    """

    observation: MachineObservation | None
    machine_discovery_succeeded: bool
    hardware_discovery_succeeded: bool
    inventory_change: object | None
    error: str | None

    @property
    def succeeded(self) -> bool:
        return (
            self.machine_discovery_succeeded
            and self.hardware_discovery_succeeded
            and self.observation is not None
        )


class MachineInventoryRefresher:
    """
    Connect platform discovery to persistent machine knowledge.

    Discovery remains responsible for obtaining facts. Inventory remains
    responsible for knowledge lifecycle. This class only coordinates the
    transition between those layers.
    """

    def __init__(
        self,
        machine_discovery: MachineDiscovery,
        hardware_discovery: HardwareDiscovery,
    ) -> None:
        self._machine_discovery = machine_discovery
        self._hardware_discovery = hardware_discovery

    def refresh(
        self,
        inventory: MachineInventory,
        *,
        known_machine_id: str | None = None,
    ) -> MachineRefreshResult:
        if not isinstance(inventory, MachineInventory):
            raise TypeError(
                "inventory must be a MachineInventory."
            )

        if (
            known_machine_id is not None
            and not isinstance(known_machine_id, str)
        ):
            raise TypeError(
                "known_machine_id must be a string or None."
            )

        if (
            known_machine_id is not None
            and not known_machine_id.strip()
        ):
            raise ValueError(
                "known_machine_id must not be empty."
            )

        try:
            machine_result = self._machine_discovery.discover()
        except Exception as exc:
            inventory_change = None

            if known_machine_id is not None:
                inventory_change = inventory.invalidate(
                    known_machine_id
                )

            return MachineRefreshResult(
                observation=None,
                machine_discovery_succeeded=False,
                hardware_discovery_succeeded=False,
                inventory_change=inventory_change,
                error=(
                    "Machine discovery failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        try:
            hardware_result = self._hardware_discovery.discover()
        except Exception as exc:
            inventory_change = inventory.invalidate(
                machine_result.identity.machine_id
            )

            return MachineRefreshResult(
                observation=None,
                machine_discovery_succeeded=True,
                hardware_discovery_succeeded=False,
                inventory_change=inventory_change,
                error=(
                    "Hardware discovery failed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        observation = self._build_observation(
            machine_result,
            hardware_result,
        )

        inventory_change = inventory.record(
            observation
        )

        return MachineRefreshResult(
            observation=observation,
            machine_discovery_succeeded=True,
            hardware_discovery_succeeded=True,
            inventory_change=inventory_change,
            error=None,
        )

    @staticmethod
    def _build_observation(
        machine_result: MachineDiscoveryResult,
        hardware_result: HardwareDiscoveryResult,
    ) -> MachineObservation:
        if not isinstance(
            machine_result,
            MachineDiscoveryResult,
        ):
            raise TypeError(
                "machine_result must be a MachineDiscoveryResult."
            )

        if not isinstance(
            hardware_result,
            HardwareDiscoveryResult,
        ):
            raise TypeError(
                "hardware_result must be a HardwareDiscoveryResult."
            )

        observed_at = machine_result.observed_at

        verification = MachineVerification(
            first_observed_at=observed_at,
            last_verified_at=observed_at,
            source=(
                f"{machine_result.source};"
                f"{hardware_result.source}"
            ),
        )

        profile = MachineProfile(
            identity=machine_result.identity,
            operating_system=machine_result.operating_system,
            virtualization=hardware_result.virtualization,
            hardware=hardware_result.hardware,
            verification=verification,
        )

        return MachineObservation(
            profile=profile,
            observed_at=observed_at,
            verified_at=observed_at,
            provenance=ObservationProvenance(
                source_type=ObservationSource.MACHINE_DISCOVERY,
                source_name=(
                    f"{machine_result.source};"
                    f"{hardware_result.source}"
                ),
            ),
            state=ObservationState.VERIFIED,
        )