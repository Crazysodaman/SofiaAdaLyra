from pathlib import Path, PurePosixPath

import pytest

from sofia.distributed.systemd_agent_service import (
    SERVICE_NAME,
    SystemdFleetAgentSpec,
    render_unit,
)


def spec() -> SystemdFleetAgentSpec:
    return SystemdFleetAgentSpec(
        python_path=PurePosixPath("/opt/sofia-fleet/.venv/bin/python"),
        config_path=PurePosixPath("/etc/sofia/fleet-agent.json"),
        state_directory=PurePosixPath("/var/lib/sofia-fleet"),
        service_user="sofia-fleet",
    )


def test_systemd_unit_is_boot_persistent_and_restartable():
    unit = render_unit(spec())

    assert "WantedBy=multi-user.target" in unit
    assert "Restart=on-failure" in unit
    assert "RestartSec=5s" in unit
    assert (
        "ExecStart=/opt/sofia-fleet/.venv/bin/python "
        "-m sofia.distributed.agent_main "
        "--config /etc/sofia/fleet-agent.json"
    ) in unit


def test_systemd_unit_has_basic_hardening_and_bounded_write_path():
    unit = render_unit(spec())

    assert "NoNewPrivileges=true" in unit
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=true" in unit
    assert "PrivateDevices=true" in unit
    assert "ReadWritePaths=/var/lib/sofia-fleet" in unit


def test_systemd_spec_requires_absolute_paths():
    with pytest.raises(ValueError, match="absolute"):
        SystemdFleetAgentSpec(
            python_path=PurePosixPath("python"),
            config_path=PurePosixPath("/etc/sofia/fleet-agent.json"),
            state_directory=PurePosixPath("/var/lib/sofia-fleet"),
        )


def test_service_name_is_stable():
    assert SERVICE_NAME == "sofia-fleet-agent.service"
