"""Production UI source contracts for attended Option C approvals.

Author regression source only. Do not execute or fake Windows Hello here.
"""
from __future__ import annotations

import sqlite3

import pytest

from sofia.platform.safe import owner_approval_ui
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_protected_settings_ui_calls_real_web_authn_without_actor_only_approvals():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src/sofia/modules/ui/settings_window.py"
    ).read_text(encoding="utf-8")

    model_begin = source.index("def approve_model_installation()")
    model_end = source.index("install_button = ttk.Button(", model_begin)
    model = source[model_begin:model_end]
    assert "select_security_key_for_settings(" in model
    assert 'authorize_exact_action(' in model
    assert 'capability="cognition.model.install"' in model
    assert 'credential_id=credential_id' in model
    assert "ExecutionApproval(" not in model
    assert "execution_approvals.record(" not in model
    assert model.index("authorize_exact_action(") < model.index(
        "install_approved_configured_model("
    )
    assert 'installation_feedback.put(' in model

    fleet_begin = source.index("def approve_fleet_candidate()")
    fleet_end = source.index("fleet_buttons = ttk.Frame(", fleet_begin)
    fleet = source[fleet_begin:fleet_end]
    assert "select_security_key_for_settings(" in fleet
    assert 'capability="fleet.enroll"' in fleet
    assert 'authorize_exact_action(' in fleet
    assert "ExecutionApproval(" not in fleet
    assert "execution_approvals.record(" not in fleet
    assert fleet.index("authorize_exact_action(") < fleet.index("enroll_candidate(")
    assert "fleet_feedback.put(" in fleet
    assert 'daemon=False' in fleet


def test_settings_rejects_unenrolled_fido2_without_opening_browser(
    tmp_path, monkeypatch,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    monkeypatch.setattr(
        owner_approval_ui, "require_owner_windows_account",
        lambda _path: "S-1-5-21-OWNER",
    )
    verifier = owner_approval_ui.OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872",
    )
    with pytest.raises(PermissionError, match="no enrolled security_key owner credential"):
        owner_approval_ui.select_security_key_for_settings(
            state, parent=None,
        )


def test_settings_can_select_an_enrolled_key_from_trusted_account(
    tmp_path, monkeypatch,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    monkeypatch.setattr(
        owner_approval_ui, "require_owner_windows_account",
        lambda _path: "S-1-5-21-OWNER",
    )
    owner_approval_ui.OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872",
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id,public_key_der,credential_kind,sign_count,enrolled_at) "
            "VALUES(?,?,?,?,?)",
            ("owner-fido2-id", b"fixture-only", "security_key", 0,
             "2026-10-11T16:00:00+00:00"),
        )
    assert owner_approval_ui.select_security_key_for_settings(
        state, parent=None,
    ) == "owner-fido2-id"
