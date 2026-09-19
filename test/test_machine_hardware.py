from pathlib import Path

import pytest

import sofia.machine.hardware as hardware_module
from sofia.machine.hardware import (
    HardwareDiscoveryResult,
    LinuxHardwareDiscovery,
    UnsupportedHardwareDiscovery,
    WindowsHardwareDiscovery,
    create_hardware_discovery,
)
from sofia.machine.model import (
    HardwareProfile,
    PlatformFamily,
    VirtualizationInfo,
)


def test_hardware_discovery_result_is_structured_and_immutable() -> None:
    result = UnsupportedHardwareDiscovery().discover()

    assert isinstance(
        result,
        HardwareDiscoveryResult,
    )
    assert isinstance(
        result.hardware,
        HardwareProfile,
    )
    assert isinstance(
        result.virtualization,
        VirtualizationInfo,
    )
    assert result.source == (
        "unsupported-platform-hardware-discovery"
    )

    with pytest.raises(AttributeError):
        result.source = "changed"


def test_unsupported_hardware_discovery_returns_unknown_hardware() -> None:
    result = UnsupportedHardwareDiscovery().discover()

    assert result.hardware.cpu is None
    assert result.hardware.gpu == ()
    assert result.hardware.memory_bytes is None
    assert result.hardware.storage == ()
    assert result.hardware.network_adapters == ()


def test_windows_discovery_rejects_non_windows_platform(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    with pytest.raises(RuntimeError):
        WindowsHardwareDiscovery().discover()


def test_linux_discovery_rejects_non_linux_platform(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    with pytest.raises(RuntimeError):
        LinuxHardwareDiscovery().discover()


def test_factory_selects_linux_hardware_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    result = create_hardware_discovery()

    assert isinstance(
        result,
        LinuxHardwareDiscovery,
    )


def test_factory_selects_windows_hardware_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    result = create_hardware_discovery()

    assert isinstance(
        result,
        WindowsHardwareDiscovery,
    )


def test_factory_selects_unsupported_hardware_discovery(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "freebsd",
    )

    result = create_hardware_discovery()

    assert isinstance(
        result,
        UnsupportedHardwareDiscovery,
    )


def test_windows_cpu_discovery_uses_cim_result(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    discovery = WindowsHardwareDiscovery()

    monkeypatch.setattr(
        discovery,
        "_powershell",
        lambda command: "AMD Ryzen Test CPU",
    )

    assert discovery._discover_cpu() == "AMD Ryzen Test CPU"


def test_windows_gpu_discovery_returns_unique_devices(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    discovery = WindowsHardwareDiscovery()

    monkeypatch.setattr(
        discovery,
        "_powershell",
        lambda command: (
            "NVIDIA Test GPU\n"
            "NVIDIA Test GPU\n"
            "AMD Test GPU"
        ),
    )

    assert discovery._discover_gpu() == (
        "NVIDIA Test GPU",
        "AMD Test GPU",
    )


def test_windows_memory_discovery_parses_bytes(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    discovery = WindowsHardwareDiscovery()

    monkeypatch.setattr(
        discovery,
        "_powershell",
        lambda command: "17179869184",
    )

    assert discovery._discover_memory() == 17179869184


def test_windows_failed_command_produces_unknown_value(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "win32",
    )

    discovery = WindowsHardwareDiscovery()

    monkeypatch.setattr(
        discovery,
        "_powershell",
        lambda command: None,
    )

    assert discovery._discover_cpu() is None
    assert discovery._discover_gpu() == ()
    assert discovery._discover_memory() is None
    assert discovery._discover_storage() == ()
    assert discovery._discover_network() == ()


def test_linux_memory_discovery_reads_meminfo(
    monkeypatch,
    tmp_path: Path,
) -> None:
    meminfo = tmp_path / "meminfo"

    meminfo.write_text(
        "MemTotal:       16384000 kB\n"
        "MemFree:         1000000 kB\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        hardware_module,
        "_LINUX_MEMINFO",
        meminfo,
    )

    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    discovery = LinuxHardwareDiscovery()

    assert discovery._discover_memory() == (
        16384000 * 1024
    )


def test_linux_cpu_discovery_reads_cpuinfo(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cpuinfo = tmp_path / "cpuinfo"

    cpuinfo.write_text(
        "processor\t: 0\n"
        "model name\t: Test Linux CPU\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        hardware_module,
        "_LINUX_CPUINFO",
        cpuinfo,
    )

    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    discovery = LinuxHardwareDiscovery()

    assert discovery._discover_cpu() == "Test Linux CPU"


def test_linux_gpu_discovery_reads_drm_evidence(
    monkeypatch,
    tmp_path: Path,
) -> None:
    card = tmp_path / "card0" / "device"
    card.mkdir(parents=True)

    (card / "vendor").write_text(
        "0x10de",
        encoding="utf-8",
    )

    (card / "device").write_text(
        "0x2684",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        hardware_module,
        "_LINUX_DRM_PATH",
        tmp_path,
    )

    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    discovery = LinuxHardwareDiscovery()

    assert discovery._discover_gpu() == (
        "0x10de 0x2684",
    )


def test_linux_failed_memory_observation_is_unknown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing"

    monkeypatch.setattr(
        hardware_module,
        "_LINUX_MEMINFO",
        missing,
    )

    monkeypatch.setattr(
        hardware_module.sys,
        "platform",
        "linux",
    )

    discovery = LinuxHardwareDiscovery()

    assert discovery._discover_memory() is None