"""Hephaestus host mutations only use exact FIDO2-signed owner approvals.

Written as a source regression. This suite is not executed during the
owner-requested code-only Workstream 1 development campaign.
"""
from pathlib import Path


_SOURCE = (
    Path(__file__).resolve().parents[1] / "src/sofia/ui/settings_sections.py"
)


def test_internal_network_staging_requires_signed_exact_fido2_before_remote_effect():
    source = _SOURCE.read_text(encoding="utf-8")
    start = source.index("def owner_stage_internal_link():")
    end = source.index("network_stage_button=ttk.Button(", start)
    body = source[start:end]
    assert 'select_security_key_for_settings(' in body
    assert 'capability="workshop.network.create"' in body
    assert 'parameters=exact' in body
    assert 'credential_id=credential_id' in body
    assert "ExecutionApproval(" not in body
    assert "ExecutionApprovalVerifier(" not in body
    assert body.index("def stage_worker():") < body.index(
        "authorize_exact_action("
    ) < body.index("stage_approved_internal_network(")
    assert 'approval_id=approval.approval_id' in body
    assert 'network_stage_queue.put(' in body


def test_workshop_installer_boot_requires_fido2_before_requesting_host_boot():
    source = _SOURCE.read_text(encoding="utf-8")
    start = source.index("def owner_install_debian():")
    end = source.index("boot_button=ttk.Button(", start)
    body = source[start:end]
    assert "select_security_key_for_settings(" in body
    assert 'capability="workshop.guest.bootstrap"' in body
    assert 'parameters=exact' in body
    assert 'credential_id=credential_id' in body
    assert "ExecutionApproval(" not in body
    assert "ExecutionApprovalVerifier(" not in body
    assert body.index("def boot_worker():") < body.index(
        "authorize_exact_action("
    ) < body.index("start_owner_approved_installer(")
    assert 'approval_id=approval.approval_id' in body
    assert "boot_queue.put(" in body


def test_no_other_actor_only_execution_receipt_is_created_in_workshop_settings():
    source = _SOURCE.read_text(encoding="utf-8")
    assert "ExecutionApproval(" not in source
    assert 'approved_by="owner:interactive"' not in source
    assert 'ExecutionApprovalVerifier(config.state_path).record(' not in source
