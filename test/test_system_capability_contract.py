from datetime import datetime, timezone

import pytest

from sofia.system import (
    NetworkInterfaceInspection,
    NetworkInspection,
    NetworkRouteInspection,
    ProcessInspection,
    ServiceInspection,
    SystemCapability,
    SystemCapabilityBackend,
    SystemCapabilityName,
    SystemCapabilityRequest,
    SystemCapabilityResult,
    SystemCapabilityResultKind,
    SystemInspection,
)


def test_canonical_capability_names_are_stable() -> None:
    assert SystemCapabilityName.PROCESS_INSPECT.value == "process.inspect"
    assert SystemCapabilityName.SYSTEM_INSPECT.value == "system.inspect"
    assert SystemCapabilityName.NETWORK_INSPECT.value == "network.inspect"
    assert SystemCapabilityName.SERVICE_INSPECT.value == "service.inspect"
    assert SystemCapabilityName.HARDWARE_INSPECT.value == "hardware.inspect"


def test_capability_is_immutable() -> None:
    capability = SystemCapability(
        name=SystemCapabilityName.SYSTEM_INSPECT,
        description="Inspect operating-system state.",
    )

    with pytest.raises(Exception):
        capability.name = SystemCapabilityName.PROCESS_INSPECT


def test_capability_rejects_invalid_name() -> None:
    with pytest.raises(TypeError):
        SystemCapability(
            name="system.inspect",
            description="Inspect operating-system state.",
        )


def test_capability_rejects_empty_description() -> None:
    with pytest.raises(ValueError):
        SystemCapability(
            name=SystemCapabilityName.SYSTEM_INSPECT,
            description=" ",
        )


def test_request_is_immutable() -> None:
    capability = SystemCapability(
        name=SystemCapabilityName.PROCESS_INSPECT,
        description="Inspect running processes.",
    )

    request = SystemCapabilityRequest(
        capability=capability,
        parameters={"pid": 1234},
    )

    with pytest.raises(Exception):
        request.capability = capability


@pytest.mark.parametrize(
    "parameter",
    [
        "command",
        "commands",
        "cmd",
        "shell",
        "script",
        "executable",
        "argv",
        "arguments",
    ],
)
def test_request_rejects_arbitrary_execution_parameters(
    parameter: str,
) -> None:
    capability = SystemCapability(
        name=SystemCapabilityName.SYSTEM_INSPECT,
        description="Inspect operating-system state.",
    )

    with pytest.raises(ValueError):
        SystemCapabilityRequest(
            capability=capability,
            parameters={parameter: "whoami"},
        )


def test_result_success_requires_structured_evidence_and_metadata() -> None:
    observed_at = datetime.now(timezone.utc)

    result = SystemCapabilityResult(
        capability=SystemCapabilityName.SYSTEM_INSPECT,
        kind=SystemCapabilityResultKind.SUCCESS,
        evidence={"hostname": "test-host"},
        observed_at=observed_at,
        backend_name="test.backend",
    )

    assert result.evidence == {"hostname": "test-host"}
    assert result.observed_at == observed_at
    assert result.backend_name == "test.backend"


def test_success_without_evidence_is_rejected() -> None:
    with pytest.raises(ValueError):
        SystemCapabilityResult(
            capability=SystemCapabilityName.SYSTEM_INSPECT,
            kind=SystemCapabilityResultKind.SUCCESS,
            observed_at=datetime.now(timezone.utc),
            backend_name="test.backend",
        )


def test_success_without_backend_is_rejected() -> None:
    with pytest.raises(ValueError):
        SystemCapabilityResult(
            capability=SystemCapabilityName.SYSTEM_INSPECT,
            kind=SystemCapabilityResultKind.SUCCESS,
            evidence={"hostname": "test-host"},
            observed_at=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize(
    "kind",
    [
        SystemCapabilityResultKind.UNAVAILABLE,
        SystemCapabilityResultKind.UNSUPPORTED,
        SystemCapabilityResultKind.FAILED,
    ],
)
def test_non_success_results_cannot_claim_evidence(
    kind: SystemCapabilityResultKind,
) -> None:
    with pytest.raises(ValueError):
        SystemCapabilityResult(
            capability=SystemCapabilityName.SYSTEM_INSPECT,
            kind=kind,
            evidence={"hostname": "test-host"},
            error="inspection failed",
        )


def test_process_inspection_contract() -> None:
    process = ProcessInspection(
        pid=1234,
        name="python",
        executable="/usr/bin/python",
        state="running",
        memory_bytes=1024,
    )

    assert process.pid == 1234
    assert process.name == "python"
    assert process.memory_bytes == 1024


def test_process_inspection_rejects_negative_pid() -> None:
    with pytest.raises(ValueError):
        ProcessInspection(pid=-1)


def test_system_inspection_contract() -> None:
    system = SystemInspection(
        hostname="venus",
        operating_system="Windows",
        architecture="AMD64",
        is_virtual_machine=False,
    )

    assert system.hostname == "venus"
    assert system.operating_system == "Windows"
    assert system.is_virtual_machine is False


def test_network_inspection_contract() -> None:
    interface = NetworkInterfaceInspection(
        name="Ethernet",
        state="up",
        addresses=("192.168.1.55",),
    )

    route = NetworkRouteInspection(
        destination="0.0.0.0/0",
        gateway="192.168.1.254",
        interface="Ethernet",
    )

    network = NetworkInspection(
        interfaces=(interface,),
        routes=(route,),
        dns_servers=("192.168.1.254",),
    )

    assert network.interfaces[0].name == "Ethernet"
    assert network.routes[0].gateway == "192.168.1.254"
    assert network.dns_servers == ("192.168.1.254",)


def test_service_inspection_contract() -> None:
    service = ServiceInspection(
        name="ssh",
        display_name="OpenSSH Server",
        state="running",
        startup_type="automatic",
    )

    assert service.name == "ssh"
    assert service.state == "running"


def test_backend_contract_is_abstract() -> None:
    with pytest.raises(TypeError):
        SystemCapabilityBackend()


def test_result_states_are_distinct() -> None:
    assert len(SystemCapabilityResultKind) == 4
    assert (
        SystemCapabilityResultKind.SUCCESS
        != SystemCapabilityResultKind.UNAVAILABLE
    )
    assert (
        SystemCapabilityResultKind.UNSUPPORTED
        != SystemCapabilityResultKind.FAILED
    )