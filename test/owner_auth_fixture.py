"""Synthetic credential fixture for real SAFE WebAuthn assertion validation.

Test-only provisioning deliberately bypasses FIRST enrollment because real
production enrollment requires an independent operator trust ceremony. It does
not bypass the cryptographic assertion verifier or approval receipt binding.
"""
from __future__ import annotations

import base64
from datetime import timedelta
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.execution_approval import ExecutionApproval, ExecutionApprovalVerifier
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def record_verified_owner_approval(
    store: ExecutionApprovalVerifier, approval: ExecutionApproval,
    *, credential_kind: str = "security_key",
) -> None:
    """Create a fresh test P-256 signer and prove exact, one-use approval."""
    if not isinstance(store, ExecutionApprovalVerifier):
        raise TypeError("canonical execution verifier required")
    if not isinstance(approval, ExecutionApproval):
        raise TypeError("typed execution approval required")
    auth = OwnerWebAuthnVerifier(
        store.path, rp_id="localhost", origin="http://localhost:39872",
    )
    key = ec.generate_private_key(ec.SECP256R1())
    credential = _b64(uuid4().bytes)
    public_der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    with sqlite3.connect(store.path) as db:
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id, public_key_der, credential_kind, sign_count, enrolled_at) "
            "VALUES (?,?,?,?,?)",
            (credential, public_der, credential_kind, 0,
             (approval.approved_at - timedelta(seconds=2)).isoformat()),
        )
    start = approval.approved_at - timedelta(seconds=2)
    pending = auth.issue(
        credential_id=credential,
        action_fingerprint=approval.request_fingerprint,
        now=start,
    )
    raw_client = json.dumps({
        "type": "webauthn.get",
        "challenge": pending["challenge"],
        "origin": "http://localhost:39872",
        "crossOrigin": False,
    }, separators=(",", ":")).encode()
    auth_data = sha256(b"localhost").digest() + bytes([0x05]) + (1).to_bytes(4, "big")
    signature = key.sign(
        auth_data + sha256(raw_client).digest(), ec.ECDSA(hashes.SHA256()),
    )
    receipt = auth.verify(
        challenge=pending["challenge"], credential_id=credential,
        action_fingerprint=approval.request_fingerprint,
        security_key_required=(credential_kind == "security_key"),
        client_data_json=_b64(raw_client),
        authenticator_data=_b64(auth_data),
        signature=_b64(signature),
        now=approval.approved_at - timedelta(seconds=1),
    )
    store.record(
        approval,
        authentication_event_id=receipt["authentication_event_id"],
    )


def resume_with_signed_owner_proof(store, *, reason: str, now=None):
    """Use a genuine synthetic FIDO2 challenge to clear a test-only stop."""
    from datetime import datetime, timezone
    from sofia.safe.execution_approval import execution_fingerprint
    from sofia.safe.operator_stop import OperatorStopStore

    if not isinstance(store, OperatorStopStore):
        raise TypeError("durable operator stop store required")
    moment = now or datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability="operator.stop.resume",
        request_fingerprint=execution_fingerprint(
            "operator.stop.resume", {"active": False, "reason": reason},
        ),
        approved_by="Sparks", approved_at=moment,
        expires_at=moment + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(store.path), approval,
    )
    return store.set(
        active=False, updated_by="Sparks", reason=reason,
        at=moment, approval_id=approval.approval_id,
    )
