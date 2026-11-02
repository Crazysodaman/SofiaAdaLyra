"""Security regressions for attended software owner credentials."""
from datetime import datetime, timezone

import pytest

from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.owner_secret import OwnerSecretStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


def test_owner_secret_bound_to_exact_action_and_one_use(tmp_path, monkeypatch):
    from sofia.platform.safe import owner_secret
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-SOFIA-OWNER",
    )
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = OwnerSecretStore(state)
    secret = "ab" * 32
    store.enroll(secret)
    assert store.enabled()
    with pytest.raises(PermissionError):
        store.enroll(secret)
    from sofia.platform.safe.execution_approval import (
        ExecutionApproval, execution_fingerprint,
    )
    from datetime import timedelta
    from uuid import uuid4
    params = {"scope": "only-owner"}
    fingerprint = execution_fingerprint("safe.permission.private_authority.change", params)
    with pytest.raises(PermissionError):
        store.authenticate("ff" * 32, action_fingerprint=fingerprint)
    event_id = store.authenticate(secret, action_fingerprint=fingerprint)
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="safe.permission.private_authority.change",
        request_fingerprint=fingerprint, approved_by="Sparks",
        approved_at=now, expires_at=now + timedelta(seconds=90),
    )
    verifier = ExecutionApprovalVerifier(state)
    verifier.record(approval, authentication_event_id=event_id)
    assert verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability=approval.capability,
        parameters=params, now=now,
    )
    assert not verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability=approval.capability,
        parameters={"scope": "wider"}, now=now,
    )
    with pytest.raises(PermissionError):
        verifier.record(
            ExecutionApproval(
                approval_id=str(uuid4()), capability=approval.capability,
                request_fingerprint=fingerprint, approved_by="Sparks",
                approved_at=now, expires_at=now + timedelta(seconds=90),
            ),
            authentication_event_id=event_id,
        )
    verifier.consume(
        approval_id=approval.approval_id, capability=approval.capability,
        parameters=params, now=now,
    )
    assert not verifier.matches_unconsumed(
        approval_id=approval.approval_id, capability=approval.capability,
        parameters=params, now=now,
    )


def test_rotation_revokes_unconsumed_software_proofs(tmp_path, monkeypatch):
    from sofia.platform.safe import owner_secret
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-SOFIA-OWNER",
    )
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = OwnerSecretStore(state)
    store.enroll("11" * 32)
    fingerprint = "a" * 64
    proof_id = store.authenticate("11" * 32, action_fingerprint=fingerprint)
    store.rotate("11" * 32, "22" * 32)
    from sofia.platform.safe.execution_approval import ExecutionApproval
    from datetime import timedelta
    from uuid import uuid4
    now = datetime.now(timezone.utc)
    with pytest.raises(PermissionError, match="unavailable or revoked"):
        ExecutionApprovalVerifier(state).record(
            ExecutionApproval(
                approval_id=str(uuid4()), capability="fleet.enroll",
                request_fingerprint=fingerprint, approved_by="Sparks",
                approved_at=now, expires_at=now + timedelta(seconds=90),
            ),
            authentication_event_id=proof_id,
        )
    with pytest.raises(PermissionError):
        store.authenticate("11" * 32, action_fingerprint=fingerprint)
    assert store.authenticate("22" * 32, action_fingerprint=fingerprint).startswith("owner-secret:")


def test_private_chat_authority_uses_software_proof(tmp_path, monkeypatch):
    """The persisted adult-chat projection must not silently require FIDO2."""
    from sofia.platform.safe import owner_secret
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-SOFIA-OWNER",
    )
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    secret = "44" * 32
    software = OwnerSecretStore(state)
    software.enroll(secret)
    from sofia.platform.safe.permissions import (
        PermissionStore, private_authority_parameters,
    )
    from sofia.platform.safe.execution_approval import (
        ExecutionApproval, execution_fingerprint,
    )
    from datetime import timedelta
    from uuid import uuid4
    permissions = PermissionStore(state)
    flags = private_authority_parameters(
        private_chat=True, adult_chat=True, adult_avatar=False,
        adult_external_delivery=False,
    )
    fp = execution_fingerprint("safe.permission.private_authority.change", flags)
    evidence = software.authenticate(secret, action_fingerprint=fp)
    moment = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="safe.permission.private_authority.change",
        request_fingerprint=fp, approved_by="Sparks", approved_at=moment,
        expires_at=moment + timedelta(seconds=90),
    )
    ExecutionApprovalVerifier(state).record(
        approval, authentication_event_id=evidence,
    )
    permissions.set_private_adult_authority(**flags, approval_id=approval.approval_id)
    assert permissions.private_adult_authority().adult_chat is True
    assert permissions.private_adult_authority().adult_external_delivery is False
    software.rotate(secret, "55" * 32)
    assert permissions.private_adult_authority().adult_chat is False


def test_owner_secret_requires_attended_owner_sid(tmp_path, monkeypatch):
    from sofia.platform.safe import owner_secret
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-OWNER",
    )
    store = OwnerSecretStore(state)
    store.enroll("77" * 32)
    monkeypatch.setattr(
        owner_secret, "require_venus_interactive_windows",
        lambda *, require_terminal=False: "S-1-5-21-ANOTHER-USER",
    )
    with pytest.raises(PermissionError):
        store.authenticate("77" * 32, action_fingerprint="f" * 64)
