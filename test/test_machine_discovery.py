from datetime import datetime, timezone
from pathlib import Path

import pytest

import sofia.machine.discovery as discovery_module
from sofia.machine.discovery import (
    LinuxMachineDiscovery,
    MachineDiscoveryResult,
    UnsupportedMachineDiscovery,
    WindowsMachineDiscovery,
    create_machine_discovery,
)
from sofia.machine.model import PlatformFamily


def test_discovery_result_is_structured_and_immutable() -> None:
    result = UnsupportedMachineDiscovery(
        system_name="TestOS"
    ).discover()

    assert isinstance(
        result,
        MachineDiscoveryResult,
    )
    assert result.identity.hostname
    assert result.operating_system.family is PlatformFamily.UNKNOWN
    assert isinstance(
        result.observed_at,
        datetime,
    )
    assert result.observed_at.tzinfo is not None
    assert result.source == "unsupported-platform-discovery"

    with pytest.raises(AttributeError):
        result.source = "changed"


def test_unsupported_discovery_does_not_claim_known_platform() -> None:
    result = UnsupportedMachineDiscovery(
        system_name="Plan9"
    ).discover()

    assert result.operating_system.family is PlatformFamily.UNKNOWN
    assert result.operating_system.name == "Plan9"


def test_linux_machine_id_is_read_from_machine_id_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    machine_id_path = tmp_path / "machine-id"
    machine_id_path.write_text(
        "test-machine-id\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        discovery_module,
        "_MACHINE_ID_PATH",
        machine_id_path,
    )

    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "linux",
    )

    monkeypatch.setattr(
        discovery_module.socket,
        "gethostname",
        lambda: "test-linux-host",
    )

    result = LinuxMachineDiscovery().discover()

    assert result.identity.machine_id == "test-machine-id"
    assert result.identity.hostname == "test-linux-host"
    assert result.operating_system.family is PlatformFamily.LINUX
    assert result.source == "linux-native-discovery"


def test_linux_machine_id_falls_back_to_hostname(
    monkeypatch,
    tmp_path: Path,
) -> None:
    machine_id_path = tmp_path / "machine-id"

    monkeypatch.setattr(
        discovery_module,
        "_MACHINE_ID_PATH",
        machine_id_path,
    )

    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "linux",
    )

    monkeypatch.setattr(
        discovery_module.socket,
        "gethostname",
        lambda: "fallback-linux-host",
    )

    result = LinuxMachineDiscovery().discover()

    assert (
        result.identity.machine_id
        == "hostname:fallback-linux-host"
    )


def test_linux_os_name_is_read_from_os_release(
    monkeypatch,
    tmp_path: Path,
) -> None:
    machine_id_path = tmp_path / "machine-id"
    machine_id_path.write_text(
        "test-id",
        encoding="utf-8",
    )

    os_release_path = tmp_path / "os-release"
    os_release_path.write_text(
        'NAME="Arch Linux"\n'
        'PRETTY_NAME="Arch Linux"\n'
        'VERSION_ID="rolling"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        discovery_module,
        "_MACHINE_ID_PATH",
        machine_id_path,
    )

    original_path_class = discovery_module.Path

    def path_factory(value):
        if value == "/etc/os-release":
            return os_release_path

        return original_path_class(value)

    monkeypatch.setattr(
        discovery_module,
        "Path",
        path_factory,
    )

    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "linux",
    )

    result = LinuxMachineDiscovery().discover()

    assert result.operating_system.name == "Arch Linux"
    assert result.operating_system.version == "rolling"


def test_windows_discovery_rejects_non_windows_platform(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "linux",
    )

    with pytest.raises(RuntimeError):
        WindowsMachineDiscovery().discover()


def test_linux_discovery_rejects_non_linux_platform(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "win32",
    )

    with pytest.raises(RuntimeError):
        LinuxMachineDiscovery().discover()


def test_factory_selects_linux_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "linux",
    )

    result = create_machine_discovery()

    assert isinstance(
        result,
        LinuxMachineDiscovery,
    )


def test_factory_selects_windows_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "win32",
    )

    result = create_machine_discovery()

    assert isinstance(
        result,
        WindowsMachineDiscovery,
    )


def test_factory_selects_unsupported_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        discovery_module.sys,
        "platform",
        "freebsd",
    )

    result = create_machine_discovery()

    assert isinstance(
        result,
        UnsupportedMachineDiscovery,
    )


def test_discovery_result_requires_timezone_aware_observation() -> None:
    from sofia.machine.model import (
        MachineIdentity,
        OperatingSystemInfo,
    )

    result = MachineDiscoveryResult(
        identity=MachineIdentity(
            machine_id="machine",
            hostname="host",
        ),
        operating_system=OperatingSystemInfo(
            family=PlatformFamily.UNKNOWN,
        ),
        observed_at=datetime.now(timezone.utc),
        source="test",
    )

    assert result.observed_at.tzinfo is not None