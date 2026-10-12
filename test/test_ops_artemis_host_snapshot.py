"""Fixed read-only SYSTEM snapshot producer / restricted consumer contract."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

import pytest

from sofia.ops import artemis_controller as controller
from sofia.ops import artemis_host_snapshot as snap


VM_ID = UUID("d4f9f4ae-caec-46f0-852b-8e65e9de8d2f")
NOW = datetime(2026, 10, 12, tzinfo=timezone.utc)


def config(tmp_path):
    root = tmp_path / "ArtemisController"
    root.mkdir(exist_ok=True)
    journal = root / "audit"
    journal.mkdir(exist_ok=True)
    (root / "trusted").mkdir(exist_ok=True)
    return controller.ArtemisControllerConfig(
        expected_vm_id=VM_ID, audit_directory=journal,
    )


def inventory(*, vm_id=VM_ID, name="Sofia", state="Running"):
    return {
        "host_inventory": {"VmId": str(vm_id), "Name": name, "State": state},
        "read_only_review": {
            "inventory_eligible_for_review": False,
            "host_blockers": ["external_virtual_switch_requires_operator_review"],
            "may_activate_canonical_writer": False,
        },
        "canonical_writer_active": "unverified",
        "activation_authorized": False,
    }


def produce(cfg, *, now=NOW, report=None):
    return snap.export_snapshot(
        cfg, inventory=lambda: inventory() if report is None else report,
        hostname=lambda: "Artemis", require_system=lambda: None,
        now=lambda: now,
    )


def test_host_export_and_restricted_controller_receipt(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    seen = []
    export = snap.export_snapshot(
        cfg, inventory=lambda: seen.append("read") or inventory(),
        hostname=lambda: "Artemis", require_system=lambda: seen.append("system"),
        now=lambda: NOW,
    )
    assert seen == ["system", "read"]
    assert set(export) == {
        "schema", "source", "host", "vm_id", "name", "state", "observed_at",
    }
    assert export["vm_id"] == str(VM_ID)
    path = cfg.audit_directory.parent / "trusted" / "sofia-host-vm-observation.json"
    assert json.loads(path.read_text()) == export
    observer = snap.ArtemisHostSnapshotObserver(
        config=cfg, now=lambda: NOW + timedelta(seconds=60),
    )
    inventory_result = observer()
    assert inventory_result["host_inventory"]["Name"] == "Sofia"
    assert inventory_result["read_only_review"]["inventory_eligible_for_review"] is False
    assert inventory_result["activation_authorized"] is False

    # The actual controller should select the file consumer, not the Hyper-V
    # WMI provider or Get-VM from a long-running LocalService.
    original = snap.ArtemisHostSnapshotObserver

    def injected(*, config):
        return original(config=config, now=lambda: NOW + timedelta(seconds=60))

    monkeypatch.setattr(snap, "ArtemisHostSnapshotObserver", injected)
    receipt = controller.controller_once(cfg, hostname=lambda: "Artemis")
    assert receipt["outcome"] == "requires_review"
    assert receipt["vm_id"] == str(VM_ID)
    assert receipt["vm_state"] == "Running"
    assert "privileged_snapshot_only" in receipt["blockers"]
    assert receipt["old_writer_fenced"] is False
    assert receipt["guest_os_verified"] is False
    assert receipt["migration_authorized"] is False
    assert receipt["host_change_performed"] is False
    assert controller.ArtemisControllerJournal(cfg.audit_directory).inspect()[0] == 1


@pytest.mark.parametrize("payload,reason", [
    ({"name": "Hephaestus"}, "host_snapshot_source_untrusted"),
    ({"vm_id": str(UUID("1cb0a329-c97e-4eff-a3fb-35600bb57411"))},
        "host_snapshot_wrong_vm"),
    ({"source": "user_input"}, "host_snapshot_source_untrusted"),
    ({"host": "Venus"}, "host_snapshot_source_untrusted"),
    ({"schema": True}, "host_snapshot_source_untrusted"),
    ({"state": ""}, "host_snapshot_vm_state_invalid"),
    ({"state": 2}, "host_snapshot_vm_state_invalid"),
    ({"observed_at": "2020-01-01T00:00:00+00:00"}, "host_snapshot_stale_or_future"),
    ({"observed_at": "2026-10-12T00:30:00+00:00"}, "host_snapshot_stale_or_future"),
    ({"observed_at": "2026-10-12T00:00:00"}, "host_snapshot_time_zone_missing"),
    ({"extra": "authority"}, "host_snapshot_schema_invalid"),
])
def test_tampered_untrusted_or_stale_snapshot_refused(tmp_path, payload, reason):
    cfg = config(tmp_path)
    produce(cfg)
    path = snap._snapshot_path(cfg)
    data = json.loads(path.read_text())
    data.update(payload)
    path.write_text(json.dumps(data))
    with pytest.raises(controller.ArtemisControllerError, match=reason):
        snap.ArtemisHostSnapshotObserver(config=cfg, now=lambda: NOW)()


def test_snapshot_missing_and_source_failure_never_claim_fencing(tmp_path):
    cfg = config(tmp_path)
    observed = controller.observe_exact_sofia(
        cfg, inventory=snap.ArtemisHostSnapshotObserver(config=cfg, now=lambda: NOW),
        hostname=lambda: "Artemis", now=lambda: NOW,
    )
    assert observed.outcome == "unavailable"
    assert observed.blockers == ("host_snapshot_missing_or_untrusted",)
    assert observed.observed_vm_id is None
    assert observed.payload()["migration_authorized"] is False
    assert observed.payload()["old_writer_fenced"] is False
    with pytest.raises(controller.ArtemisControllerError, match="failed verification"):
        produce(cfg, report=inventory(vm_id=UUID("1cb0a329-c97e-4eff-a3fb-35600bb57411")))
    assert not snap._snapshot_path(cfg).exists()


def test_export_never_calls_inventory_before_system_identity(tmp_path):
    cfg = config(tmp_path)
    seen = []

    def refused():
        seen.append("denied")
        raise controller.ArtemisControllerError("SYSTEM-only")

    with pytest.raises(controller.ArtemisControllerError, match="SYSTEM-only"):
        snap.export_snapshot(
            cfg, inventory=lambda: seen.append("inventory") or inventory(),
            hostname=lambda: "Artemis", require_system=refused,
            now=lambda: NOW,
        )
    assert seen == ["denied"]
    assert not snap._snapshot_path(cfg).exists()


def test_wrong_host_does_not_publish(tmp_path):
    cfg = config(tmp_path)
    with pytest.raises(controller.ArtemisControllerError, match="Artemis"):
        snap.export_snapshot(
            cfg, inventory=lambda: inventory(),
            hostname=lambda: "Venus", require_system=lambda: None,
            now=lambda: NOW,
        )
    assert not snap._snapshot_path(cfg).exists()
