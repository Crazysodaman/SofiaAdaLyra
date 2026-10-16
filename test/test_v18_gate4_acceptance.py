"""Evidence-only Gate 4 authentication requires external independent keys."""
from __future__ import annotations

import base64
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from sofia.verify.v18_gate4_acceptance import (
    REGISTRY_SCHEMA, authenticate_review, load_review_receipts,
)
from sofia.verify.v18_roadmap import RoadmapIntegrityError

pytestmark = pytest.mark.pkg_verify


def certificate(private_key, *, task="CA-103"):
    statement = {
        "task_id": task, "reviewed_revision": "a" * 40,
        "original_requirement_sha256": sha256(b"one exact requirement").hexdigest(),
        "gate4_proof_sha256": "c" * 64, "ci_run_id": 12345,
        "review_evidence_path": "docs/review.md",
        "review_evidence_sha256": sha256(b"independent review").hexdigest(),
        "decision": "accepted_gate4",
        "all_original_requirements_verified": True,
        "independent_test_coverage_verified": True,
        "original_host_trials_verified_if_required": True,
    }
    payload = json.dumps({"reviewer_id": "external-reviewer", "statement": statement},
                         sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {
        "reviewer_id": "external-reviewer", "statement": statement,
        "signature": base64.b64encode(private_key.sign(payload)).decode(),
    }


def proof():
    return [{"gate": k} for k in range(1, 4)] + [{
        "gate": 4, "revision": "a" * 40, "sha256": "c" * 64,
        "ci": {"run_id": 12345},
    }]


def public_key(private):
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def test_missing_external_trust_anchor_cannot_certify(monkeypatch, tmp_path):
    private = Ed25519PrivateKey.generate()
    assert authenticate_review(
        tmp_path, task_id="CA-103", original_requirement="one exact requirement",
        proofs=proof(), certificate=certificate(private), trusted_keys={},
    ) is False


def test_matching_signed_independent_receipt_can_be_authenticated(monkeypatch, tmp_path):
    private = Ed25519PrivateKey.generate()
    from sofia.verify import v18_gate4_acceptance
    monkeypatch.setattr(v18_gate4_acceptance, "_git_blob",
                        lambda root, path: b"independent review")
    assert authenticate_review(
        tmp_path, task_id="CA-103", original_requirement="one exact requirement",
        proofs=proof(), certificate=certificate(private),
        trusted_keys={"external-reviewer": public_key(private)},
    ) is True


def test_changed_original_requirement_or_forged_signer_fails_closed(monkeypatch, tmp_path):
    private = Ed25519PrivateKey.generate()
    from sofia.verify import v18_gate4_acceptance
    monkeypatch.setattr(v18_gate4_acceptance, "_git_blob",
                        lambda root, path: b"independent review")
    signed = certificate(private)
    keys = {"external-reviewer": public_key(private)}
    with pytest.raises(RoadmapIntegrityError, match="source"):
        authenticate_review(
            tmp_path, task_id="CA-103", original_requirement="different requirement",
            proofs=proof(), certificate=signed, trusted_keys=keys,
        )
    with pytest.raises(RoadmapIntegrityError, match="signature"):
        authenticate_review(
            tmp_path, task_id="CA-103", original_requirement="one exact requirement",
            proofs=proof(), certificate=signed,
            trusted_keys={"external-reviewer": public_key(Ed25519PrivateKey.generate())},
        )


def test_different_review_bytes_fail_even_with_valid_signature(monkeypatch, tmp_path):
    private = Ed25519PrivateKey.generate()
    from sofia.verify import v18_gate4_acceptance
    monkeypatch.setattr(v18_gate4_acceptance, "_git_blob",
                        lambda root, path: b"changed by a different commit")
    with pytest.raises(RoadmapIntegrityError, match="changed"):
        authenticate_review(
            tmp_path, task_id="CA-103", original_requirement="one exact requirement",
            proofs=proof(), certificate=certificate(private),
            trusted_keys={"external-reviewer": public_key(private)},
        )


def test_independent_review_manifest_is_empty_until_trusted_reviewer_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("SOFIA_GATE4_TRUSTED_REVIEWER_KEYS", raising=False)
    root = tmp_path / "repo"
    path = root / "docs/development/v18-gate4-independent-acceptance.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": REGISTRY_SCHEMA, "certificates": []}))
    records, keys = load_review_receipts(root)
    assert records == {}
    assert keys == {}


def test_acceptance_not_awarded_from_unsigned_or_duplicate_manifest(tmp_path):
    root = tmp_path / "repo"
    path = root / "docs/development/v18-gate4-independent-acceptance.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema": REGISTRY_SCHEMA, "certificates": [
        {"reviewer_id": "self-asserted", "statement": {}, "signature": ""},
    ]}))
    with pytest.raises(RoadmapIntegrityError, match="incomplete"):
        load_review_receipts(root)
