from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from sofia.application.act_service import SofiaActService
from sofia.application.fleet_runtime import (
    create_fleet_bootstrap_coordinator,
    create_fleet_reconciliation_notifier,
)
from sofia.config.model import FleetBootstrapConfiguration
from sofia.ops import InstallAuthority
from sofia.ops.reconciliation_journal import FleetReconciliationRecord


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


def test_fleet_reconciliation_notice_is_durable_and_non_authoritative(
    monkeypatch,
    tmp_path,
):
    state = tmp_path / "state.db"
    with sqlite3.connect(state):
        pass
    act = SofiaActService(state)
    monkeypatch.setenv(
        "SOFIA_NOTIFICATION_HA_SERVICE",
        "notify_sofia",
    )
    notifier = create_fleet_reconciliation_notifier(
        act_service=act,
    )
    assert notifier is not None

    now = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)
    record = FleetReconciliationRecord(
        proposal_key="fleet-repair:test",
        drift_kind="workload_placement",
        subject_id="plex",
        expected="artemis",
        observed="venus",
        proposal_kind="workload_migration",
        reason="review migration",
        first_seen=now,
        last_seen=now,
        active=True,
    )

    notifier(record)
    notifier(record)

    with sqlite3.connect(state) as db:
        rows = db.execute(
            """
            SELECT notice_id,evidence_id,content,status
            FROM act_system_notice
            """
        ).fetchall()

    assert len(rows) == 1
    notice_id, evidence_id, content, status = rows[0]
    assert notice_id == "fleet-reconcile:fleet-repair:test"
    assert evidence_id == "fleet-repair:test"
    assert "proposal only" in content
    assert "no repair has been authorized or executed" in content
    assert status == "queued"
