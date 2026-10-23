from sofia.platform.machine.comparison import (
    ObservationChange,
    ObservationComparison,
    compare_machine_observations,
)
from sofia.platform.machine.discovery import (
    LinuxMachineDiscovery,
    MachineDiscovery,
    MachineDiscoveryResult,
    UnsupportedMachineDiscovery,
    WindowsMachineDiscovery,
    create_machine_discovery,
)
from sofia.platform.machine.hardware import (
    HardwareDiscovery,
    HardwareDiscoveryResult,
    LinuxHardwareDiscovery,
    UnsupportedHardwareDiscovery,
    WindowsHardwareDiscovery,
    create_hardware_discovery,
)
from sofia.platform.machine.inventory import MachineInventory
from sofia.platform.machine.location import (
    MachineLocationRecord,
    MachineLocationRegistry,
    new_machine_location,
)
from sofia.platform.machine.model import (
    HardwareProfile,
    MachineIdentity,
    MachineProfile,
    MachineVerification,
    NetworkAdapterInfo,
    OperatingSystemInfo,
    PlatformFamily,
    StorageDeviceInfo,
    VirtualizationInfo,
)
from sofia.platform.machine.observation import (
    MachineObservation,
    ObservationProvenance,
    ObservationSource,
    ObservationState,
)
from sofia.platform.machine.refresh import (
    MachineInventoryRefresher,
    MachineRefreshResult,
)


__all__ = [
    "HardwareDiscovery",
    "HardwareDiscoveryResult",
    "HardwareProfile",
    "LinuxHardwareDiscovery",
    "LinuxMachineDiscovery",
    "MachineDiscovery",
    "MachineDiscoveryResult",
    "MachineIdentity",
    "MachineInventory",
    "MachineInventoryRefresher",
    "MachineLocationRecord",
    "MachineLocationRegistry",
    "MachineObservation",
    "MachineProfile",
    "MachineRefreshResult",
    "MachineVerification",
    "NetworkAdapterInfo",
    "ObservationChange",
    "ObservationComparison",
    "ObservationProvenance",
    "ObservationSource",
    "ObservationState",
    "OperatingSystemInfo",
    "PlatformFamily",
    "StorageDeviceInfo",
    "UnsupportedHardwareDiscovery",
    "UnsupportedMachineDiscovery",
    "VirtualizationInfo",
    "WindowsHardwareDiscovery",
    "WindowsMachineDiscovery",
    "compare_machine_observations",
    "create_hardware_discovery",
    "create_machine_discovery",
    "new_machine_location",
]