from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sofia.system.linux import LinuxSystemCapabilityBackend
from sofia.system.model import (
    SystemCapability,
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResultKind,
)


def capability(
    name: SystemCapabilityName,
) -> SystemCapability:
    return SystemCapability(
        name=name,
        description=f"Test capability: {name.value}",
    )


def request(
    name: SystemCapabilityName,
    parameters: dict | None = None,
) -> SystemCapabilityRequest:
    return SystemCapabilityRequest(
        capability=capability(name),
        parameters=parameters or {},
    )


def write(
    root: Path,
    relative: str,
    content: str,
) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        content,
        encoding="utf-8",
    )


@pytest.fixture
def linux_roots(tmp_path: Path) -> tuple[Path, Path, Path]:
    proc = tmp_path / "proc"
    sys = tmp_path / "sys"
    etc = tmp_path / "etc"

    proc.mkdir()
    sys.mkdir()
    etc.mkdir()

    return proc, sys, etc


def test_supported_capabilities() -> None:
    backend = LinuxSystemCapabilityBackend()

    assert {
        capability.name
        for capability in backend.supported_capabilities
    } == {
        SystemCapabilityName.PROCESS_INSPECT,
        SystemCapabilityName.SYSTEM_INSPECT,
        SystemCapabilityName.NETWORK_INSPECT,
        SystemCapabilityName.SERVICE_INSPECT,
    }


def test_non_linux_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Windows",
    )

    backend = LinuxSystemCapabilityBackend()

    result = backend.execute(
        request(SystemCapabilityName.PROCESS_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.UNSUPPORTED
    assert result.evidence is None


def test_process_inspection_reads_proc(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(proc, "uptime", "100.00 50.00\n")
    write(proc, "123/comm", "python\n")

    write(
        proc,
        "123/stat",
        "123 (python) S 1 2 3 4 5 6 7 8 9 10 11 12 13 "
        "14 15 16 17 18 19 20 21 22 23 24\n",
    )

    write(
        proc,
        "123/status",
        "Name:\tpython\n"
        "VmRSS:\t2048 kB\n",
    )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    monkeypatch.setattr(
        "sofia.system.linux.os.readlink",
        lambda path: "/usr/bin/python",
    )

    result = backend.execute(
        request(
            SystemCapabilityName.PROCESS_INSPECT,
            {"pid": 123},
        )
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    processes = result.evidence["processes"]

    assert len(processes) == 1
    assert processes[0].pid == 123
    assert processes[0].name == "python"
    assert processes[0].state == "S"
    assert processes[0].executable == "/usr/bin/python"
    assert processes[0].memory_bytes == 2048 * 1024


def test_process_limit_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(proc, "uptime", "100.00 50.00\n")

    for pid in (10, 20, 30):
        write(proc, f"{pid}/comm", f"process-{pid}\n")
        write(
            proc,
            f"{pid}/stat",
            f"{pid} (process-{pid}) S 1 2 3 4 5 6 7 8 9 10 "
            "11 12 13 14 15 16 17 18 19 20 21 22 23 24\n",
        )
        write(
            proc,
            f"{pid}/status",
            "VmRSS:\t1 kB\n",
        )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.PROCESS_INSPECT,
            {"limit": 2},
        )
    )

    processes = result.evidence["processes"]

    assert [item.pid for item in processes] == [10, 20]


def test_process_rejects_unknown_parameter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.PROCESS_INSPECT,
            {"unknown": True},
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_system_inspection_reads_os_and_kernel(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )
    monkeypatch.setattr(
        "sofia.system.linux.socket.gethostname",
        lambda: "artemis",
    )
    monkeypatch.setattr(
        "sofia.system.linux.platform.machine",
        lambda: "x86_64",
    )
    monkeypatch.setattr(
        "sofia.system.linux.platform.release",
        lambda: "6.12.1-test",
    )

    write(
        etc,
        "os-release",
        'NAME="Arch Linux"\n'
        'PRETTY_NAME="Arch Linux"\n'
        'VERSION_ID="2026.09.01"\n',
    )

    write(proc, "uptime", "1234.50 100.00\n")

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.SYSTEM_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    system = result.evidence["system"]

    assert system.hostname == "artemis"
    assert system.operating_system == "Arch Linux"
    assert system.operating_system_version == "2026.09.01"
    assert system.architecture == "x86_64"
    assert system.kernel == "6.12.1-test"
    assert system.uptime_seconds == 1234.50


def test_system_detects_vmware(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(proc, "uptime", "100.00 50.00\n")
    write(
        etc,
        "os-release",
        'NAME="Ubuntu"\n',
    )

    write(
        sys,
        "class/dmi/id/product_name",
        "VMware Virtual Platform\n",
    )
    write(
        sys,
        "class/dmi/id/sys_vendor",
        "VMware, Inc.\n",
    )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.SYSTEM_INSPECT)
    )

    system = result.evidence["system"]

    assert system.is_virtual_machine is True
    assert system.hypervisor == "VMware"


def test_system_inspection_rejects_unknown_parameter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.SYSTEM_INSPECT,
            {"unknown": True},
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED


def test_network_reads_interfaces_routes_dns(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(
        sys,
        "class/net/eth0/operstate",
        "up\n",
    )
    write(
        sys,
        "class/net/eth0/address",
        "00:11:22:33:44:55\n",
    )
    write(
        sys,
        "class/net/eth0/statistics/rx_bytes",
        "1000\n",
    )
    write(
        sys,
        "class/net/eth0/statistics/tx_bytes",
        "2000\n",
    )

    write(
        sys,
        "class/net/lo/operstate",
        "unknown\n",
    )
    write(
        sys,
        "class/net/lo/address",
        "00:00:00:00:00:00\n",
    )

    write(
        proc,
        "net/route",
        "Iface Destination Gateway Flags RefCnt Use Metric "
        "Mask MTU Window IRTT\n"
        "eth0 00000000 0101A8C0 0003 0 0 100 "
        "00000000 0 0 0\n",
    )

    write(
        etc,
        "resolv.conf",
        "nameserver 1.1.1.1\n"
        "nameserver 8.8.8.8\n",
    )

    command_output = json.dumps(
        [
            {
                "ifname": "eth0",
                "addr_info": [
                    {
                        "family": "inet",
                        "local": "192.168.1.20",
                        "prefixlen": 24,
                    },
                    {
                        "family": "inet6",
                        "local": "fe80::1",
                        "prefixlen": 64,
                    },
                ],
            },
            {
                "ifname": "lo",
                "addr_info": [
                    {
                        "family": "inet",
                        "local": "127.0.0.1",
                        "prefixlen": 8,
                    },
                ],
            },
        ]
    )

    commands: list[tuple[str, ...]] = []

    def runner(command: tuple[str, ...]) -> str:
        commands.append(command)
        return command_output

    backend = LinuxSystemCapabilityBackend(
        command_runner=runner,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.NETWORK_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    network = result.evidence["network"]

    assert len(network.interfaces) == 2

    eth0 = network.interfaces[0]

    assert eth0.name == "eth0"
    assert eth0.state == "up"
    assert eth0.addresses == (
        "192.168.1.20",
        "fe80::1",
    )
    assert eth0.mac_address == "00:11:22:33:44:55"
    assert eth0.received_bytes == 1000
    assert eth0.transmitted_bytes == 2000

    assert network.routes[0].destination == "0.0.0.0"
    assert network.routes[0].gateway == "192.168.1.1"
    assert network.routes[0].interface == "eth0"

    assert network.dns_servers == (
        "1.1.1.1",
        "8.8.8.8",
    )

    assert commands == [
        (
            "ip",
            "-j",
            "address",
            "show",
        )
    ]


def test_network_interface_filter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    for name in ("eth0", "eth1"):
        write(
            sys,
            f"class/net/{name}/operstate",
            "up\n",
        )
        write(
            sys,
            f"class/net/{name}/address",
            "00:11:22:33:44:55\n",
        )

    write(
        proc,
        "net/route",
        "Iface Destination Gateway Flags RefCnt Use Metric "
        "Mask MTU Window IRTT\n",
    )

    write(
        etc,
        "resolv.conf",
        "nameserver 1.1.1.1\n",
    )

    output = json.dumps(
        [
            {
                "ifname": "eth0",
                "addr_info": [],
            },
            {
                "ifname": "eth1",
                "addr_info": [],
            },
        ]
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: output,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.NETWORK_INSPECT,
            {"interface": "eth1"},
        )
    )

    network = result.evidence["network"]

    assert [item.name for item in network.interfaces] == [
        "eth1"
    ]


def test_network_invalid_json_fails(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(
        sys,
        "class/net/eth0/operstate",
        "up\n",
    )
    write(
        sys,
        "class/net/eth0/address",
        "00:11:22:33:44:55\n",
    )
    write(
        proc,
        "net/route",
        "Iface Destination Gateway Flags RefCnt Use Metric "
        "Mask MTU Window IRTT\n",
    )
    write(
        etc,
        "resolv.conf",
        "",
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: "not-json",
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.NETWORK_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.FAILED
    assert result.evidence is None


def test_service_inspection_uses_fixed_systemctl_command(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    commands: list[tuple[str, ...]] = []

    service_output = (
        "Id=ssh.service\n"
        "Description=OpenSSH server daemon\n"
        "ActiveState=active\n"
        "SubState=running\n"
        "UnitFileState=enabled\n"
        "Id=cron.service\n"
        "Description=Regular background program processing daemon\n"
        "ActiveState=inactive\n"
        "SubState=dead\n"
        "UnitFileState=disabled\n"
    )

    def runner(command: tuple[str, ...]) -> str:
        commands.append(command)
        return service_output

    backend = LinuxSystemCapabilityBackend(
        command_runner=runner,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.SERVICE_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.SUCCESS

    services = result.evidence["services"]

    assert len(services) == 2

    assert services[0].name == "ssh.service"
    assert services[0].display_name == (
        "OpenSSH server daemon"
    )
    assert services[0].state == "active"
    assert services[0].startup_type == "enabled"

    assert services[1].name == "cron.service"
    assert services[1].state == "inactive"

    assert commands == [
        (
            "systemctl",
            "show",
            "--type=service",
            "--all",
            "--no-pager",
            "--no-legend",
            "--property=Id,Description,ActiveState,"
            "SubState,UnitFileState",
        )
    ]


def test_service_name_filter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    output = (
        "Id=ssh.service\n"
        "Description=SSH\n"
        "ActiveState=active\n"
        "SubState=running\n"
        "UnitFileState=enabled\n"
        "Id=cron.service\n"
        "Description=Cron\n"
        "ActiveState=inactive\n"
        "SubState=dead\n"
        "UnitFileState=disabled\n"
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: output,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"name": "cron.service"},
        )
    )

    services = result.evidence["services"]

    assert len(services) == 1
    assert services[0].name == "cron.service"


def test_service_state_filter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    output = (
        "Id=ssh.service\n"
        "Description=SSH\n"
        "ActiveState=active\n"
        "SubState=running\n"
        "UnitFileState=enabled\n"
        "Id=cron.service\n"
        "Description=Cron\n"
        "ActiveState=inactive\n"
        "SubState=dead\n"
        "UnitFileState=disabled\n"
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: output,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"state": "active"},
        )
    )

    services = result.evidence["services"]

    assert len(services) == 1
    assert services[0].name == "ssh.service"


def test_service_limit(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    output = (
        "Id=a.service\n"
        "Description=A\n"
        "ActiveState=active\n"
        "SubState=running\n"
        "UnitFileState=enabled\n"
        "Id=b.service\n"
        "Description=B\n"
        "ActiveState=active\n"
        "SubState=running\n"
        "UnitFileState=enabled\n"
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: output,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"limit": 1},
        )
    )

    services = result.evidence["services"]

    assert len(services) == 1
    assert services[0].name == "a.service"


def test_service_rejects_unknown_parameter(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    backend = LinuxSystemCapabilityBackend(
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.SERVICE_INSPECT,
            {"unknown": True},
        )
    )

    assert result.kind is SystemCapabilityResultKind.FAILED


def test_service_command_failure_is_failed(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    def runner(command: tuple[str, ...]) -> str:
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
        )

    backend = LinuxSystemCapabilityBackend(
        command_runner=runner,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.SERVICE_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.FAILED


def test_missing_ip_command_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    write(
        sys,
        "class/net/eth0/operstate",
        "up\n",
    )
    write(
        sys,
        "class/net/eth0/address",
        "00:11:22:33:44:55\n",
    )
    write(
        proc,
        "net/route",
        "Iface Destination Gateway Flags RefCnt Use Metric "
        "Mask MTU Window IRTT\n",
    )
    write(
        etc,
        "resolv.conf",
        "",
    )

    def runner(command: tuple[str, ...]) -> str:
        raise FileNotFoundError("ip")

    backend = LinuxSystemCapabilityBackend(
        command_runner=runner,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(SystemCapabilityName.NETWORK_INSPECT)
    )

    assert result.kind is SystemCapabilityResultKind.UNAVAILABLE


def test_network_limit(
    monkeypatch: pytest.MonkeyPatch,
    linux_roots: tuple[Path, Path, Path],
) -> None:
    proc, sys, etc = linux_roots

    monkeypatch.setattr(
        "sofia.system.linux.platform.system",
        lambda: "Linux",
    )

    for name in ("eth0", "eth1", "eth2"):
        write(
            sys,
            f"class/net/{name}/operstate",
            "up\n",
        )
        write(
            sys,
            f"class/net/{name}/address",
            "00:11:22:33:44:55\n",
        )

    write(
        proc,
        "net/route",
        "Iface Destination Gateway Flags RefCnt Use Metric "
        "Mask MTU Window IRTT\n",
    )

    write(
        etc,
        "resolv.conf",
        "",
    )

    output = json.dumps(
        [
            {"ifname": "eth0", "addr_info": []},
            {"ifname": "eth1", "addr_info": []},
            {"ifname": "eth2", "addr_info": []},
        ]
    )

    backend = LinuxSystemCapabilityBackend(
        command_runner=lambda command: output,
        proc_root=proc,
        sys_root=sys,
        etc_root=etc,
    )

    result = backend.execute(
        request(
            SystemCapabilityName.NETWORK_INSPECT,
            {"limit": 2},
        )
    )

    network = result.evidence["network"]

    assert [item.name for item in network.interfaces] == [
        "eth0",
        "eth1",
    ]