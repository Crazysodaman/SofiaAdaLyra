"""Owner-signed permission changes: production boundary regression source.

Tests are intentionally not executed during Workstream 1 code-only delivery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import sqlite3

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
    projected = store.grants()
    assert len(projected) == 1
    assert projected[0].owner_authenticated is True
    assert store.allows_standing(
        "storage.mkdir", exact, now=NOW + timedelta(seconds=1),
    ) is True
    assert store.allows_standing(
        "storage.mkdir", {**exact, "path": "another"},
        now=NOW + timedelta(seconds=1),
    ) is False
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


def test_legacy_actor_only_standing_grant_is_quarantined_without_erasing_history(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_permission_grant "
            "(grant_id,capability,scope_json,granted_by,granted_at,"
            "expires_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
            ("legacy-grant", "storage.mkdir", '{"root_index":0}',
             "Sparks", NOW.isoformat(), None),
        )
    grants = store.grants()
    assert len(grants) == 1
    assert grants[0].owner_authenticated is False
    assert grants[0].is_active_at(NOW + timedelta(seconds=1)) is False
    assert store.grants(active_only=True) == ()
    assert store.allows_standing(
        "storage.mkdir", {"root_index": 0}, now=NOW + timedelta(seconds=1),
    ) is False


def test_revoking_signing_owner_key_invalidates_existing_standing_grant(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    grant = grant_with_signed_owner(
        store, "storage.mkdir", scope={"root_index": 0},
        grant_id="owner-bound-grant", now=NOW,
    )
    assert grant.owner_authenticated is True
    assert store.allows_standing(
        "storage.mkdir", {"root_index": 0}, now=NOW + timedelta(seconds=1),
    ) is True
    with sqlite3.connect(state) as db:
        credential = db.execute(
            "SELECT ch.credential_id FROM safe_permission_owner_auth_binding b "
            "JOIN safe_execution_owner_auth_binding auth "
            "ON auth.approval_id=b.approval_id "
            "JOIN safe_owner_challenge ch "
            "ON auth.authentication_event_id="
            "('owner-webauthn:' || ch.challenge_digest) "
            "WHERE b.grant_id=?",
            (grant.grant_id,),
        ).fetchone()
        assert credential is not None
        # Only model the already-authorized revocation's durable result.
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=? "
            "WHERE credential_id=?",
            ((NOW + timedelta(seconds=2)).isoformat(), credential[0]),
        )
    assert store.grants()[0].owner_authenticated is False
    assert store.allows_standing(
        "storage.mkdir", {"root_index": 0}, now=NOW + timedelta(seconds=3),
    ) is False


def test_old_actor_only_adult_flags_do_not_survive_authentication_upgrade(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_private_adult_authority SET "
            "private_chat=0,adult_chat=1,adult_avatar=1,"
            "adult_external_delivery=1,updated_by='Sparks' WHERE singleton=1"
        )
    effective = store.private_adult_authority()
    assert effective.private_chat is False
    assert effective.adult_chat is False
    assert effective.adult_avatar is False
    assert effective.adult_external_delivery is False
    assert effective.updated_by == "system:unverified"


def test_revoked_fido2_key_fences_its_level5_private_authority(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    flags = {
        "private_chat": False,
        "adult_chat": True,
        "adult_avatar": True,
        "adult_external_delivery": False,
    }
    private_with_signed_owner(store, **flags, now=NOW)
    active = store.private_adult_authority()
    assert active.private_chat is False
    assert active.adult_chat is True
    assert active.adult_avatar is True
    with sqlite3.connect(state) as db:
        cred = db.execute(
            "SELECT ch.credential_id "
            "FROM safe_private_authority_auth_binding b "
            "JOIN safe_execution_owner_auth_binding auth "
            "ON auth.approval_id=b.approval_id "
            "JOIN safe_owner_challenge ch ON "
            "auth.authentication_event_id=('owner-webauthn:' || ch.challenge_digest) "
            "WHERE b.singleton=1"
        ).fetchone()
        assert cred is not None
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=? "
            "WHERE credential_id=?",
            ((NOW + timedelta(seconds=2)).isoformat(), cred[0]),
        )
    effective = store.private_adult_authority()
    assert effective.private_chat is False
    assert effective.adult_chat is False
    assert effective.adult_avatar is False
    assert effective.adult_external_delivery is False


def test_modified_stored_grant_scope_cannot_reuse_legitimate_owner_signature(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    grant = grant_with_signed_owner(
        store, "storage.mkdir",
        scope={"root_index": 0, "path": "approved"},
        grant_id="cannot-expand", now=NOW,
    )
    assert store.allows_standing(
        "storage.mkdir",
        {"root_index": 0, "path": "approved"},
        now=NOW + timedelta(seconds=1),
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_permission_grant SET scope_json=? WHERE grant_id=?",
            ('{"root_index":0,"path":"different"}', grant.grant_id),
        )
    assert store.grants()[0].owner_authenticated is False
    assert not store.allows_standing(
        "storage.mkdir",
        {"root_index": 0, "path": "different"},
        now=NOW + timedelta(seconds=2),
    )


def test_modified_level5_flags_cannot_inherit_earlier_signature(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = PermissionStore(state)
    private_with_signed_owner(
        store, private_chat=True, adult_chat=False, adult_avatar=False,
        adult_external_delivery=False, now=NOW,
    )
    assert store.private_adult_authority().adult_chat is False
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_private_adult_authority SET "
            "adult_chat=1,adult_avatar=1 WHERE singleton=1"
        )
    current = store.private_adult_authority()
    assert current.updated_by == "system:unverified"
    assert current.adult_chat is False
    assert current.adult_avatar is False
