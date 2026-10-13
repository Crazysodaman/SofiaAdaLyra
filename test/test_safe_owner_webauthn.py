"""Hybrid owner WebAuthn verification contract (authored, not executed)."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier
from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 11, 16, tzinfo=timezone.utc)
FINGERPRINT = "f" * 64


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def setup(tmp_path, kind="security_key"):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    verifier = OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872",
    )
    key = ec.generate_private_key(ec.SECP256R1())
    credential_id = b64(b"test-credential-id")
    der = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Fixture-only trusted registration; production intentionally has no
    # unauthenticated insertion/enrollment method.
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id,public_key_der,credential_kind,sign_count,enrolled_at) "
            "VALUES(?,?,?,?,?)",
            (credential_id, der, kind, 0, NOW.isoformat()),
        )
    return state, verifier, key, credential_id


def sign(key, challenge, *, origin="http://localhost:39872", count=1,
         rp_id="localhost", flags=0x05, kind=None):
    raw = json.dumps({
        "type": "webauthn.get",
        "challenge": challenge,
        "origin": origin,
        "crossOrigin": False,
    }, sort_keys=True, separators=(",", ":")).encode()
    authenticator = (
        sha256(rp_id.encode()).digest()
        + bytes([flags])
        + count.to_bytes(4, "big")
    )
    signature = key.sign(authenticator + sha256(raw).digest(), ec.ECDSA(hashes.SHA256()))
    return {
        "client_data_json": b64(raw),
        "authenticator_data": b64(authenticator),
        "signature": b64(signature),
    }


def test_verified_key_consumes_one_challenge_with_canonical_safe_audit(tmp_path):
    state, verifier, key, credential = setup(tmp_path)
    pending = verifier.issue(
        credential_id=credential, action_fingerprint=FINGERPRINT, now=NOW,
    )
    evidence = verifier.verify(
        challenge=pending["challenge"],
        credential_id=credential, action_fingerprint=FINGERPRINT,
        security_key_required=True, now=NOW + timedelta(seconds=2),
        **sign(key, pending["challenge"]),
    )
    assert evidence["credential_kind"] == "security_key"
    assert evidence["authentication_event_id"].startswith("owner-webauthn:")
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT sign_count FROM safe_owner_credential WHERE credential_id=?",
            (credential,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT event_type FROM safe_audit_event WHERE event_id=?",
            (evidence["authentication_event_id"],),
        ).fetchone() == ("owner.webauthn.verified",)
    with pytest.raises(PermissionError, match="used"):
        verifier.verify(
            challenge=pending["challenge"], credential_id=credential,
            action_fingerprint=FINGERPRINT, security_key_required=True,
            now=NOW + timedelta(seconds=3), **sign(key, pending["challenge"], count=2),
        )


@pytest.mark.parametrize("tamper", ["origin", "rp_id", "flags", "challenge", "action"])
def test_assertion_refuses_spoofed_identity_and_wrong_action(tmp_path, tamper):
    state, verifier, key, credential = setup(tmp_path)
    pending = verifier.issue(
        credential_id=credential, action_fingerprint=FINGERPRINT, now=NOW,
    )
    signed = sign(
        key, pending["challenge"],
        origin="http://evil.invalid" if tamper == "origin" else "http://localhost:39872",
        rp_id="evil.invalid" if tamper == "rp_id" else "localhost",
        flags=0x01 if tamper == "flags" else 0x05,
    )
    with pytest.raises(PermissionError):
        verifier.verify(
            challenge=b64(b"x" * 32) if tamper == "challenge" else pending["challenge"],
            credential_id=credential,
            action_fingerprint="a" * 64 if tamper == "action" else FINGERPRINT,
            security_key_required=True, now=NOW + timedelta(seconds=2),
            **signed,
        )
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_owner_challenge"
        ).fetchone() == (None,)


def test_platform_credential_cannot_satisfy_physical_key_gate(tmp_path):
    _, verifier, key, credential = setup(tmp_path, kind="platform")
    pending = verifier.issue(
        credential_id=credential, action_fingerprint=FINGERPRINT, now=NOW,
    )
    # Generic denial does not reveal whether a credential is platform,
    # expired, mis-scoped or unknown; no credential-type oracle.
    with pytest.raises(PermissionError, match="wrong-scope or used owner challenge"):
        verifier.verify(
            challenge=pending["challenge"], credential_id=credential,
            action_fingerprint=FINGERPRINT, security_key_required=True,
            now=NOW + timedelta(seconds=1), **sign(key, pending["challenge"]),
        )


def test_expired_challenge_and_non_advance_counter_are_denied(tmp_path):
    _, verifier, key, credential = setup(tmp_path)
    pending = verifier.issue(
        credential_id=credential, action_fingerprint=FINGERPRINT,
        now=NOW, ttl_seconds=15,
    )
    with pytest.raises(PermissionError, match="expired"):
        verifier.verify(
            challenge=pending["challenge"], credential_id=credential,
            action_fingerprint=FINGERPRINT, security_key_required=False,
            now=NOW + timedelta(seconds=16), **sign(key, pending["challenge"]),
        )
    verifier.verify(
        challenge=pending["challenge"], credential_id=credential,
        action_fingerprint=FINGERPRINT, security_key_required=False,
        now=NOW + timedelta(seconds=1), **sign(key, pending["challenge"], count=2),
    )
    again = verifier.issue(
        credential_id=credential, action_fingerprint=FINGERPRINT,
        now=NOW + timedelta(seconds=2),
    )
    with pytest.raises(PermissionError, match="counter"):
        verifier.verify(
            challenge=again["challenge"], credential_id=credential,
            action_fingerprint=FINGERPRINT, security_key_required=False,
            now=NOW + timedelta(seconds=3), **sign(key, again["challenge"], count=2),
        )


def test_unenrolled_credential_cannot_request_a_challenge(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    verifier = OwnerWebAuthnVerifier(
        state, rp_id="localhost", origin="http://localhost:39872"
    )
    with pytest.raises(PermissionError, match="enrolled"):
        verifier.issue(
            credential_id=b64(b"not-enrolled"),
            action_fingerprint=FINGERPRINT, now=NOW,
        )


def test_protected_approval_requires_one_fresh_owner_security_key_proof(tmp_path):
    from uuid import uuid4
    from sofia.safe.execution_approval import (
        ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
    )

    state, verifier, key, credential = setup(tmp_path)
    approver = ExecutionApprovalVerifier(state)
    exact = {"host_id": "Artemis", "node_id": "trusted-exact-node"}
    fingerprint = execution_fingerprint("fleet.enroll", exact)

    def approval(when):
        return ExecutionApproval(
            approval_id=str(uuid4()),
            capability="fleet.enroll", request_fingerprint=fingerprint,
            approved_by="Sparks", approved_at=when,
            expires_at=when + timedelta(minutes=5),
        )

    with pytest.raises(PermissionError, match="FIDO2"):
        approver.record(approval(NOW + timedelta(seconds=1)))
    challenge = verifier.issue(
        credential_id=credential, action_fingerprint=fingerprint, now=NOW,
    )
    proof = verifier.verify(
        challenge=challenge["challenge"], credential_id=credential,
        action_fingerprint=fingerprint, security_key_required=True,
        now=NOW + timedelta(seconds=1), **sign(key, challenge["challenge"]),
    )
    authenticated = approval(NOW + timedelta(seconds=2))
    approver.record(
        authenticated,
        authentication_event_id=proof["authentication_event_id"],
    )
    assert approver.matches_unconsumed(
        approval_id=authenticated.approval_id,
        capability="fleet.enroll", parameters=exact,
        now=NOW + timedelta(seconds=3),
    )
    with pytest.raises(PermissionError, match="already bound"):
        approver.record(
            approval(NOW + timedelta(seconds=3)),
            authentication_event_id=proof["authentication_event_id"],
        )
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM safe_execution_approval"
        ).fetchone()[0] == 1


def test_platform_hello_proof_cannot_be_upgraded_to_protected_fido2(tmp_path):
    from uuid import uuid4
    from sofia.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier

    state, verifier, key, credential = setup(tmp_path, kind="platform")
    proof_fp = "a" * 64
    challenge = verifier.issue(
        credential_id=credential, action_fingerprint=proof_fp, now=NOW,
    )
    proof = verifier.verify(
        challenge=challenge["challenge"], credential_id=credential,
        action_fingerprint=proof_fp, security_key_required=False,
        now=NOW + timedelta(seconds=1), **sign(key, challenge["challenge"]),
    )
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="fleet.enroll",
        request_fingerprint=proof_fp, approved_by="Sparks",
        approved_at=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
    )
    with pytest.raises(PermissionError, match="security key"):
        ExecutionApprovalVerifier(state).record(
            approval, authentication_event_id=proof["authentication_event_id"],
        )
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM safe_execution_approval"
        ).fetchone()[0] == 0


def test_preexisting_unverified_protected_approval_is_fenced_at_all_readers(tmp_path):
    """Historical actor-only rows cannot survive the auth policy upgrade."""
    from uuid import uuid4
    from sofia.safe.execution_approval import (
        ExecutionApprovalVerifier, execution_fingerprint,
    )

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    approvals = ExecutionApprovalVerifier(state)
    approval_id = str(uuid4())
    args = {"host_id": "Artemis"}
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_execution_approval "
            "(approval_id,capability,request_fingerprint,approved_by,approved_at,expires_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                approval_id, "fleet.enroll",
                execution_fingerprint("fleet.enroll", args),
                "Sparks", NOW.isoformat(),
                (NOW + timedelta(minutes=5)).isoformat(),
            ),
        )
    assert "fleet.enroll" not in approvals.active_capabilities(
        now=NOW + timedelta(seconds=1)
    )
    assert not approvals.matches_unconsumed(
        approval_id=approval_id, capability="fleet.enroll",
        parameters=args, now=NOW + timedelta(seconds=1),
    )
    with pytest.raises(PermissionError, match="verified owner"):
        approvals.consume(
            approval_id=approval_id, capability="fleet.enroll",
            parameters=args, now=NOW + timedelta(seconds=1),
        )
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone() == (None,)


def test_revoked_security_key_cannot_issue_or_preserve_unused_protected_approvals(
    tmp_path,
):
    from uuid import uuid4
    from sofia.safe.execution_approval import (
        ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
    )

    state, verifier, signer, credential = setup(tmp_path)
    args = {"host_id": "Artemis", "node_id": "reviewed"}
    fingerprint = execution_fingerprint("fleet.enroll", args)
    challenge = verifier.issue(
        credential_id=credential, action_fingerprint=fingerprint, now=NOW,
    )
    proof = verifier.verify(
        challenge=challenge["challenge"], credential_id=credential,
        action_fingerprint=fingerprint, security_key_required=True,
        now=NOW + timedelta(seconds=1),
        **sign(signer, challenge["challenge"]),
    )
    first = ExecutionApproval(
        approval_id=str(uuid4()), capability="fleet.enroll",
        request_fingerprint=fingerprint, approved_by="Sparks",
        approved_at=NOW + timedelta(seconds=2),
        expires_at=NOW + timedelta(minutes=5),
    )
    approvals = ExecutionApprovalVerifier(state)
    approvals.record(
        first, authentication_event_id=proof["authentication_event_id"],
    )
    assert approvals.matches_unconsumed(
        approval_id=first.approval_id,
        capability="fleet.enroll", parameters=args,
        now=NOW + timedelta(seconds=3),
    )

    # The production revocation endpoint requires FIDO2 authorization.
    # Test fixture simulates only its resulting canonical revoked_at state.
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=? WHERE credential_id=?",
            ((NOW + timedelta(seconds=3)).isoformat(), credential),
        )
    assert "fleet.enroll" not in approvals.active_capabilities(
        now=NOW + timedelta(seconds=4),
    )
    assert not approvals.matches_unconsumed(
        approval_id=first.approval_id,
        capability="fleet.enroll", parameters=args,
        now=NOW + timedelta(seconds=4),
    )
    with pytest.raises(PermissionError, match="verified owner"):
        approvals.consume(
            approval_id=first.approval_id,
            capability="fleet.enroll", parameters=args,
            now=NOW + timedelta(seconds=4),
        )
    with pytest.raises(PermissionError, match="revoked"):
        approvals.record(
            ExecutionApproval(
                approval_id=str(uuid4()), capability="fleet.enroll",
                request_fingerprint=fingerprint, approved_by="Sparks",
                approved_at=NOW + timedelta(seconds=4),
                expires_at=NOW + timedelta(minutes=6),
            ),
            authentication_event_id=proof["authentication_event_id"],
        )


def test_canonical_safe_approval_checks_are_safe_before_any_owner_enrollment(tmp_path):
    from sofia.safe.execution_approval import ExecutionApprovalVerifier

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    approvals = ExecutionApprovalVerifier(state)
    assert approvals.active_capabilities(now=NOW) == ()
    assert not approvals.matches_unconsumed(
        approval_id="not-enrolled",
        capability="fleet.enroll",
        parameters={"host_id":"Artemis"},
        now=NOW,
    )
    with pytest.raises(PermissionError, match="does not exist"):
        approvals.consume(
            approval_id="not-enrolled",
            capability="fleet.enroll",
            parameters={"host_id":"Artemis"},
            now=NOW,
        )
    with sqlite3.connect(state) as db:
        tables = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert {"safe_owner_credential", "safe_owner_challenge",
            "safe_execution_owner_auth_binding"} <= tables
