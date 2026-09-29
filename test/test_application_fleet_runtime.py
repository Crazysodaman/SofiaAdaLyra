from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.application.act_service import SofiaActService
from sofia.application.fleet_runtime import (
    create_fleet_bootstrap_coordinator,
)
from sofia.config.model import FleetBootstrapConfiguration
from sofia.ops import InstallAuthority


def _act(tmp_path):
    return SofiaActService(tmp_path / "state.db")


def test_disabled_fleet_bootstrap_composes_no_coordinator(tmp_path):
    configuration = SimpleNamespace(
        fleet_bootstrap=FleetBootstrapConfiguration(
            enabled=False,
        )
    )

    assert create_fleet_bootstrap_coordinator(
        configuration=configuration,
        act_service=_act(tmp_path),
    ) is None


def test_enabled_fleet_bootstrap_requires_exact_package_evidence(tmp_path):
    configuration = SimpleNamespace(
        fleet_bootstrap=FleetBootstrapConfiguration(
            enabled=True,
            authority="standing_policy",
        )
    )

    with pytest.raises(ValueError, match="package SHA-256"):
        create_fleet_bootstrap_coordinator(
            configuration=configuration,
            act_service=_act(tmp_path),
        )


def test_enabled_fleet_bootstrap_composes_planner_from_policy(tmp_path):
    configuration = SimpleNamespace(
        fleet_bootstrap=FleetBootstrapConfiguration(
            enabled=True,
            authority="standing_policy",
            package_id="sofia-fleet-agent",
            package_version="1.2.3",
            package_sha256="a" * 64,
            package_source="approved-wheel",
            protocol_version="1.0",
        )
    )

    coordinator = create_fleet_bootstrap_coordinator(
        configuration=configuration,
        act_service=_act(tmp_path),
    )

    assert coordinator is not None
    assert coordinator.authority is InstallAuthority.STANDING_POLICY
    assert coordinator.package.package_id == "sofia-fleet-agent"
    assert coordinator.package.version == "1.2.3"
    assert coordinator.package.sha256 == "a" * 64
    assert coordinator.package.source == "approved-wheel"
    assert coordinator.installer_factory is None


def test_invalid_fleet_bootstrap_protocol_rejected_early():
    with pytest.raises(ValueError, match="MAJOR.MINOR"):
        FleetBootstrapConfiguration(
            protocol_version="banana",
        )


def test_background_bootstrap_rejects_reusable_operator_approval(tmp_path):
    configuration = SimpleNamespace(
        fleet_bootstrap=FleetBootstrapConfiguration(
            enabled=True,
            authority="operator_approved",
            package_sha256="a" * 64,
            package_source="approved-wheel",
        )
    )

    with pytest.raises(ValueError, match="cannot be configured"):
        create_fleet_bootstrap_coordinator(
            configuration=configuration,
            act_service=_act(tmp_path),
        )
