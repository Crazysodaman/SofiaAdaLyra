"""D028 exact signed module manifest digest and independent signer tests.

Synthetic Ed25519 keys are not publisher enrollment or production trust.
This does not admit modules into the B1 cache or run their code.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import replace
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sofia.platform.modules.library_signed_manifest import (
    SignedModuleLibraryRejected, verify_publisher_signed_module_manifest,
)
from test.test_module_package_v1 import manifest, signed


@pytest.fixture
def signed_module():
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    original = manifest((("module.py", sha256(b"inert").hexdigest()),))
    candidate = signed(original, signer)
    raw = candidate.canonical_signed_bytes()
    kwargs = dict(
        raw_signed_manifest=raw,
        expected_signed_manifest_sha256=sha256(raw).hexdigest(),
        independent_publisher_public_key=public,
        expected_publisher_public_key_sha256=sha256(public).hexdigest(),
        expected_trust_ref=candidate.trust_ref,
        publisher_current=lambda _: True,
    )
    return candidate, signer, raw, kwargs


def test_exact_signed_module_bytes_have_distinct_policy_and_artifact_ids(signed_module):
    candidate, signer, raw, kwargs = signed_module
    verified = verify_publisher_signed_module_manifest(**kwargs)
    assert verified.publisher_signed_manifest_sha256 == sha256(raw).hexdigest()
    assert verified.unsigned_policy_identity_sha256 == candidate.package_identity_digest()
    assert verified.artifact_set_identity_sha256 == candidate.artifact_set_identity_digest()
    assert verified.publisher_signed_manifest_sha256 != verified.unsigned_policy_identity_sha256
    assert verified.unsigned_policy_identity_sha256 != verified.artifact_set_identity_sha256
    assert verified.still_matches(raw) is True
    assert verified.still_matches(raw + b" ") is False


def test_module_signed_bytes_change_when_signature_changes_not_policy(signed_module):
    candidate, signer, raw, kwargs = signed_module
    other = Ed25519PrivateKey.generate()
    changed = signed(replace(candidate), other)
    assert changed.package_identity_digest() == candidate.package_identity_digest()
    assert changed.publisher_signed_manifest_digest() != candidate.publisher_signed_manifest_digest()
    changed_raw = changed.canonical_signed_bytes()
    wrong = {
        **kwargs, "raw_signed_manifest": changed_raw,
        "expected_signed_manifest_sha256": sha256(changed_raw).hexdigest(),
    }
    with pytest.raises(SignedModuleLibraryRejected, match="signature"):
        verify_publisher_signed_module_manifest(**wrong)


def test_module_manifest_refuses_hub_supplied_or_wrong_publisher_root(signed_module):
    candidate, signer, raw, kwargs = signed_module
    with pytest.raises(SignedModuleLibraryRejected, match="independent publisher"):
        verify_publisher_signed_module_manifest(
            **{**kwargs, "expected_publisher_public_key_sha256": "a" * 64},
        )
    with pytest.raises(SignedModuleLibraryRejected, match="trust root"):
        verify_publisher_signed_module_manifest(
            **{**kwargs, "expected_trust_ref": "trust:other-publisher"},
        )


def test_module_manifest_refuses_revoked_publisher_and_noncanonical_bytes(signed_module):
    candidate, signer, raw, kwargs = signed_module
    with pytest.raises(SignedModuleLibraryRejected, match="revoked"):
        verify_publisher_signed_module_manifest(
            **{**kwargs, "publisher_current": lambda _: False},
        )
    noncanonical = json.dumps(
        json.loads(raw), indent=2, sort_keys=False,
    ).encode("utf-8")
    with pytest.raises(SignedModuleLibraryRejected, match="canonical"):
        verify_publisher_signed_module_manifest(
            **{**kwargs, "raw_signed_manifest": noncanonical,
               "expected_signed_manifest_sha256": sha256(noncanonical).hexdigest()},
        )


def test_module_manifest_refuses_tampering_even_with_rehashed_signed_payload(signed_module):
    candidate, signer, raw, kwargs = signed_module
    altered = json.loads(raw)
    altered["publisher"] = "other-untrusted-publisher"
    forged = json.dumps(
        altered, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()
    with pytest.raises(SignedModuleLibraryRejected, match="signature"):
        verify_publisher_signed_module_manifest(
            **{**kwargs, "raw_signed_manifest": forged,
               "expected_signed_manifest_sha256": sha256(forged).hexdigest()},
        )
