from datetime import datetime, timezone

import pytest

from sofia.machine.model import (
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


def _verification() -> MachineVerification:
    timestamp = datetime.now(timezone.utc)

    return MachineVerification(
        first_observed_at=timestamp,
        last_verified_at=timestamp,
        source="test",
    )


def test_machine_identity_requires_non_empty_strings() -> None:
    identity = MachineIdentity(
        machine_id="machine-1",
        hostname="test-host",
    )

    assert identity.machine_id == "machine-1"
    assert identity.hostname == "test-host"


@pytest.mark.parametrize(
    "machine_id",
    [None, 123, ""],
)
def test_machine_identity_rejects_invalid_machine_id(
    machine_id,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        MachineIdentity(
            machine_id=machine_id,
            hostname="test-host",
        )


def test_operating_system_info_supports_windows() -> None:
    operating_system = OperatingSystemInfo(
        family=PlatformFamily.WINDOWS,
        name="Windows 11",
        version="10.0",
        architecture="x86_64",
        kernel="Windows NT",
    )

    assert operating_system.family is PlatformFamily.WINDOWS
    assert operating_system.name == "Windows 11"


def test_operating_system_info_supports_linux() -> None:
    operating_system = OperatingSystemInfo(
        family=PlatformFamily.LINUX,
        name="Arch Linux",
        version="rolling",
        architecture="x86_64",
        kernel="6.x",
    )

    assert operating_system.family is PlatformFamily.LINUX
    assert operating_system.name == "Arch Linux"


def test_virtualization_info_represents_bare_metal() -> None:
    virtualization = VirtualizationInfo(
        is_virtual_machine=False,
    )

    assert virtualization.is_virtual_machine is False
    assert virtualization.hypervisor is None


def test_virtualization_info_represents_virtual_machine() -> None:
    virtualization = VirtualizationInfo(
        is_virtual_machine=True,
        hypervisor="Hyper-V",
        platform="virtual-machine",
    )

    assert virtualization.is_virtual_machine is True
    assert virtualization.hypervisor == "Hyper-V"


def test_hardware_profile_supports_structured_components() -> None:
    storage = StorageDeviceInfo(
        name="Disk 0",
        capacity_bytes=1_000,
        device_type="SSD",
    )

    network = NetworkAdapterInfo(
        name="Ethernet",
        mac_address="00:11:22:33:44:55",
        interface_type="ethernet",
    )

    hardware = HardwareProfile(
        cpu="Test CPU",
        gpu=("Test GPU",),
        memory_bytes=16_000,
        storage=(storage,),
        network_adapters=(network,),
    )

    assert hardware.cpu == "Test CPU"
    assert hardware.gpu == ("Test GPU",)
    assert hardware.memory_bytes == 16_000
    assert hardware.storage == (storage,)
    assert hardware.network_adapters == (network,)


def test_machine_profile_combines_environment_state() -> None:
    profile = MachineProfile(
        identity=MachineIdentity(
            machine_id="machine-1",
            hostname="test-host",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.LINUX,
            name="Arch Linux",
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        hardware=HardwareProfile(
            cpu="Test CPU",
        ),
        verification=_verification(),
    )

    assert profile.identity.hostname == "test-host"
    assert profile.operating_system.family is PlatformFamily.LINUX
    assert profile.hardware.cpu == "Test CPU"


def test_machine_profile_is_immutable() -> None:
    profile = MachineProfile(
        identity=MachineIdentity(
            machine_id="machine-1",
            hostname="test-host",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.UNKNOWN,
        ),
        virtualization=VirtualizationInfo(
            is_virtual_machine=False,
        ),
        hardware=HardwareProfile(),
        verification=_verification(),
    )

    with pytest.raises(AttributeError):
        profile.identity = MachineIdentity(
            machine_id="other",
            hostname="other",
        )


def test_verification_cannot_go_backwards_in_time() -> None:
    first = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    last = datetime(
        2025,
        1,
        1,
        tzinfo=timezone.utc,
    )

    with pytest.raises(ValueError):
        MachineVerification(
            first_observed_at=first,
            last_verified_at=last,
            source="test",
        )