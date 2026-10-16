"""CA-1206: execute representative *real production policy* boundaries.

These are bounded CI/host-independent behavioral checks, not proof that a
Venus interactive journey, a remote fleet call, or a live capture occurred.
The 34,560-case planning matrix remains explicitly not_executed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from sofia.ops.activity import ActivityMode
from sofia.ops.saga import Escalation, PartialOutcome, plan_compensation
from sofia.verify.v18_acceptance_matrix import EXAMPLES
from sofia.vision.consent import (
    propose_screen_permit,
    receipt_from_permitted_bytes,
)
from sofia.vision.desktop_control import require_workstation_clear

pytestmark = pytest.mark.pkg_verify
_NOW = datetime(2026, 10, 15, 18, 0, tzinfo=timezone.utc)


def _case(name: str) -> dict:
    for example in EXAMPLES:
        if example["name"] == name:
            assert len(example["selectors"]) == 9
            assert example["expected_safety_contract"]
            return example
    raise AssertionError(f"missing original CA-1206 scenario: {name}")


def test_gaming_blocks_venus_input_despite_fresh_normal_tray(monkeypatch, tmp_path):
    """Real desk-control gate rejects a running game even with normal tray status."""
    row = _case("Game blocks desktop input but not read-only chat")
    assert row["selectors"]["busy_state"] == "gaming"
    from sofia.ops import activity

    class State:
        override = ActivityMode.AUTO
        effective = ActivityMode.NORMAL
        source = "windows-process-inspection"
        observed_at = _NOW

    class Store:
        def __init__(self, path):
            self.path = path

        def state(self, host):
            assert host == "Venus"
            return State()

    monkeypatch.setattr(activity, "HostActivityStore", Store)
    monkeypatch.setattr("sofia.vision.desktop_control.game_process_clear", lambda: False)
    with pytest.raises(PermissionError, match="running game"):
        require_workstation_clear(tmp_path / "isolated-not-created.db", "Venus", _NOW)


def test_manual_tray_override_cannot_bypass_game_protection(monkeypatch, tmp_path):
    """Even manually overriding the tray never authorizes desktop automation."""
    from sofia.ops import activity

    class State:
        override = ActivityMode.NORMAL
        effective = ActivityMode.NORMAL
        source = "windows-process-inspection"
        observed_at = _NOW

    class Store:
        def __init__(self, path):
            self.path = path

        def state(self, host):
            return State()

    monkeypatch.setattr(activity, "HostActivityStore", Store)
    monkeypatch.setattr(
        "sofia.vision.desktop_control.game_process_clear",
        lambda: pytest.fail("game scanner should not be invoked after unsafe override"),
    )
    with pytest.raises(PermissionError, match="fresh unoverridden"):
        require_workstation_clear(tmp_path / "isolated-not-created.db", "Venus", _NOW)


def test_missing_screen_consent_scope_and_expiry_block_real_capture_receipt():
    """The actual vision consent boundary refuses any unconsented frame."""
    row = _case("No screen permission means no private pixels")
    assert row["selectors"]["permission"] == "none"
    permit = propose_screen_permit(
        principal_id="owner", audience_id="local", device_id="Venus",
        target_id="window:sample", purpose="bounded owner observation",
        kind="snapshot", at=_NOW, duration_seconds=10,
    )
    assert not permit.allows(
        principal_id="owner", audience_id="shared", device_id="Venus",
        target_id="window:sample", at=_NOW,
    )
    payload = b"nonprivate-synthetic-frame"
    with pytest.raises(PermissionError, match="OS consent"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW,
            os_picker_consented=False, protected_surface=False,
        )
    with pytest.raises(PermissionError, match="surface protected"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW,
            os_picker_consented=True, protected_surface=True,
        )
    with pytest.raises(PermissionError, match="expired"):
        receipt_from_permitted_bytes(
            permit, frame=payload, at=_NOW + timedelta(seconds=10),
            os_picker_consented=True, protected_surface=False,
        )
    receipt = receipt_from_permitted_bytes(
        permit, frame=payload, at=_NOW,
        os_picker_consented=True, protected_surface=False,
    )
    assert receipt.actual_frame_available
    assert receipt.digest_sha256 == sha256(payload).hexdigest()
    # A scope-only proposal is not proof that a real OS picker or frame was used.


def test_uncertain_device_effect_never_automatically_replays():
    """Contract used for external effects refuses retries without receiver proof."""
    row = _case("Uncertain remote effect never blindly repeats")
    assert row["selectors"]["failure"] == "uncertain_effect"
    for operation in ("home_assistant.service.call", "jmri.turnout.set"):
        plan = plan_compensation(PartialOutcome(
            operation_id=operation,
            committed_steps=("command_sent",),
            uncommitted_steps=("effect_verified",),
            external_effect_observed=False,
        ))
        assert plan.may_retry_automatically is False
        assert plan.escalation is Escalation.OPERATOR_ACTION_REQUIRED
        assert plan.compensating_actions == ()


def test_no_automated_scenario_can_claim_manual_host_completion():
    """These checks cover four policies, not six manual acceptance journeys."""
    assert len(EXAMPLES) == 6
    assert all("host_receipt" not in e and "observed_outcome" not in e for e in EXAMPLES)
