from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.dev.approval import DevApproval, DevOperation, dev_request_fingerprint
from sofia.safe.dev_approval import (
    DevApprovalVerifier,
    dev_approval_signature_payload,
)


NOW = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)


def approval():
    parameters = {"proposal_id": "code-1"}
    return DevApproval(
        approval_id="approval-1",
        operation=DevOperation.APPLY,
        proposal_id="code-1",
        request_fingerprint=dev_request_fingerprint(
            DevOperation.APPLY,
            parameters,
        ),
        approved_by="Sparks",
        approved_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )


def key_material():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, public


def test_dev_approval_requires_signature_and_is_consumed_once(tmp_path):
    private, public = key_material()
    verifier = DevApprovalVerifier(
        tmp_path / "state.db",
        trusted_keys={"sparks-dev": public},
    )
    item = approval()
    verifier.record(
        item,
        signer_key_id="sparks-dev",
        signature=private.sign(dev_approval_signature_payload(item)),
    )

    consumed = verifier.consume(
        approval_id=item.approval_id,
        operation=item.operation,
        proposal_id=item.proposal_id,
        parameters={"proposal_id": item.proposal_id},
        now=NOW + timedelta(seconds=1),
    )
    assert consumed == item
    with pytest.raises(PermissionError, match="already consumed"):
        verifier.consume(
            approval_id=item.approval_id,
            operation=item.operation,
            proposal_id=item.proposal_id,
            parameters={"proposal_id": item.proposal_id},
            now=NOW + timedelta(seconds=2),
        )


def test_dev_approval_rejects_untrusted_or_invalid_signatures(tmp_path):
    private, public = key_material()
    verifier = DevApprovalVerifier(
        tmp_path / "state.db",
        trusted_keys={"sparks-dev": public},
    )
    item = approval()

    with pytest.raises(PermissionError, match="not trusted"):
        verifier.record(
            item,
            signer_key_id="other-key",
            signature=private.sign(dev_approval_signature_payload(item)),
        )
    with pytest.raises(PermissionError, match="invalid"):
        verifier.record(
            item,
            signer_key_id="sparks-dev",
            signature=b"not-a-signature",
        )
