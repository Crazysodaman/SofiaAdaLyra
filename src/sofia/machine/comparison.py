from dataclasses import dataclass
from enum import Enum

from sofia.machine.observation import MachineObservation


class ObservationChange(str, Enum):
    NO_CHANGE = "no_change"
    CHANGED = "changed"
    BECAME_UNKNOWN = "became_unknown"
    BECAME_KNOWN = "became_known"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True)
class ObservationComparison:
    change: ObservationChange
    identity_changed: bool
    operating_system_changed: bool
    virtualization_changed: bool
    hardware_changed: bool


def compare_machine_observations(
    previous: MachineObservation,
    current: MachineObservation,
) -> ObservationComparison:
    if not isinstance(previous, MachineObservation):
        raise TypeError(
            "previous must be a MachineObservation."
        )

    if not isinstance(current, MachineObservation):
        raise TypeError(
            "current must be a MachineObservation."
        )

    identity_changed = (
        previous.profile.identity != current.profile.identity
    )

    operating_system_changed = (
        previous.profile.operating_system
        != current.profile.operating_system
    )

    virtualization_changed = (
        previous.profile.virtualization
        != current.profile.virtualization
    )

    hardware_changed = (
        previous.profile.hardware
        != current.profile.hardware
    )

    changed = (
        identity_changed
        or operating_system_changed
        or virtualization_changed
        or hardware_changed
    )

    if not changed:
        change = ObservationChange.NO_CHANGE
    elif (
        current.state.value == "unknown"
        and previous.state.value != "unknown"
    ):
        change = ObservationChange.BECAME_UNKNOWN
    elif (
        current.state.value != "unknown"
        and previous.state.value == "unknown"
    ):
        change = ObservationChange.BECAME_KNOWN
    elif current.state.value == "contradicted":
        change = ObservationChange.CONTRADICTED
    else:
        change = ObservationChange.CHANGED

    return ObservationComparison(
        change=change,
        identity_changed=identity_changed,
        operating_system_changed=operating_system_changed,
        virtualization_changed=virtualization_changed,
        hardware_changed=hardware_changed,
    )