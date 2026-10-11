"""Owner-signed permission changes: production boundary regression source.

Tests are intentionally not executed during Workstream 1 code-only delivery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.safe.permissions import (
    PermissionStore, private_authority_parameters, standing_grant_parameters,
)
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.owner_auth_fixture import (
    grant_with_signed_owner, private_with_signed_owner,
    record_verified_owner_approval, revoke_with_signed_owner,
)

NOW = datetime(2026, 10, 11, 16, 20, tzinfo=timezone.utc)


def _approval(store: PermissionStore, *, capability: str, parameters: dict):
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=capability,
        request_fingerprint=execution_fingerprint(capability, parameters),
        approved_by="Sparks", approved_at=NOW,
        expires_at=NOW + timedelta(minutes=3),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(store.path), approval,
    )
    return approval.approval_id


def test_actor_label_alone_cannot_create_revoke_or_expand_authority(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    with pytest.raises(PermissionError, match="FIDO2"):
        store.grant(
            "storage.mkdir", scope={"root_index": 0, "path": "private"},
            grant_id="no-signed-proof", granted_by="Sparks", now=NOW,
        )
    with pytest.raises(PermissionError, match="FIDO2"):
        store.revoke("nonexistent", revoked_by="Sparks", now=NOW)
    with pytest.raises(PermissionError, match="FIDO2"):
        store.set_private_adult_authority(
            private_chat=True, adult_chat=True, adult_avatar=True,
            adult_external_delivery=True, updated_by="Sparks", now=NOW,
        )
    assert store.grants() == ()
    assert store.private_adult_authority().adult_external_delivery is False


def test_signed_grant_is_single_use_and_fingerprint_binds_exact_scope(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    grant_id = "approved-mkdir"
    exact = {"root_index": 0, "path": "approved"}
    approval_id = _approval(
        store, capability="safe.permission.standing.grant",
        parameters=standing_grant_parameters(
            "storage.mkdir", scope=exact, grant_id=grant_id,
            expires_at=None,
        ),
    )
    with pytest.raises(PermissionError, match="parameters do not match"):
        store.grant(
            "storage.mkdir", scope={"root_index": 0, "path": "unapproved"},
            grant_id=grant_id, approval_id=approval_id, now=NOW,
        )
    granted = store.grant(
        "storage.mkdir", scope=exact, grant_id=grant_id,
        approval_id=approval_id, now=NOW,
    )
    assert granted.grant_id == grant_id
    with pytest.raises(PermissionError, match="already consumed"):
        store.grant(
            "storage.mkdir", scope=exact, grant_id="different-grant",
            approval_id=approval_id, now=NOW + timedelta(seconds=1),
        )


def test_signed_revoke_and_private_change_do_not_reuse_proof(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    grant = grant_with_signed_owner(
        store, "storage.mkdir",
        scope={"root_index": 0, "path": "approved"},
        grant_id="signed-initial-grant", now=NOW,
    )
    revoked = revoke_with_signed_owner(
        store, grant.grant_id, now=NOW + timedelta(seconds=1),
    )
    assert revoked.revoked_at is not None
    assert not store.allows_standing(
        "storage.mkdir", {"root_index": 0, "path": "approved"},
        now=NOW + timedelta(seconds=2),
    )

    flags = private_authority_parameters(
        private_chat=True, adult_chat=True, adult_avatar=True,
        adult_external_delivery=False,
    )
    approval_id = _approval(
        store, capability="safe.permission.private_authority.change",
        parameters=flags,
    )
    with pytest.raises(PermissionError, match="parameters do not match"):
        store.set_private_adult_authority(
            private_chat=False, adult_chat=True, adult_avatar=True,
            adult_external_delivery=False, approval_id=approval_id, now=NOW,
        )
    store.set_private_adult_authority(
        **flags, approval_id=approval_id, now=NOW,
    )
    assert store.private_adult_authority().adult_chat is True
    with pytest.raises(PermissionError, match="already consumed"):
        store.set_private_adult_authority(
            **flags, approval_id=approval_id,
            now=NOW + timedelta(seconds=1),
        )


def test_existing_ui_wires_level3_and_level5_to_signed_owner_approval():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[1]
        / "src/sofia/ui/settings_window.py"
    ).read_text(encoding="utf-8")
    grant = source[source.index("def grant_standing_permission()"):
                   source.index("def revoke_standing_permission()")]
    assert 'capability="safe.permission.standing.grant"' in grant
    assert "authorize_exact_action(" in grant
    assert "approval_id=approval.approval_id" in grant
    assert grant.index("authorize_exact_action(") < grant.index("store.grant(")
    revoke = source[source.index("def revoke_standing_permission()"):
                    source.index("grant_buttons = ttk.Frame(")]
    assert 'capability="safe.permission.standing.revoke"' in revoke
    assert "authorize_exact_action(" in revoke
    assert "approval_id=approval.approval_id" in revoke

    saving = source[source.index("    def save("):
                    source.index('    ttk.Button(\n        bottom,\n        text="Save"')]
    assert 'capability="safe.permission.private_authority.change"' in saving
    assert 'approval_id=approved_private[0]' in saving
    assert 'approved_private[1] != requested_private_authority' in saving
