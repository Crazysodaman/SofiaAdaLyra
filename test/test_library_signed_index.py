"""D028 signed index verification against disposable test keys, never release trust."""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test.library_fixture_support import make_signed_catalog_fixture

from sofia.platform.ops.library_signed_index import (
    SCHEMA, _DOMAIN, SignedLibraryIndexRejected, verify_signed_library_index,
)


@pytest.fixture
def signed_catalog():
    return make_signed_catalog_fixture()

def test_independent_publisher_index_accepts_exact_signed_bytes(signed_catalog):
    env, sign, kwargs = signed_catalog
    review = verify_signed_library_index(sign(), **kwargs)
    assert review.publisher_key_sha256 == kwargs["expected_publisher_key_sha256"]
    assert review.catalog_revision == 7
    assert review.matches(review.catalog)
    assert review.source_platform_id == "primary-library"
    # Mutation of the returned dictionary must not fabricate trusted selection.
    review.catalog["catalog_revision"] = 8
    assert not review.matches(review.catalog)


def test_signed_index_rejects_tampered_catalog(signed_catalog):
    env, sign, kwargs = signed_catalog
    candidate = json.loads(sign())
    candidate["catalog"]["target_platform_id"] = "other-recipient"
    raw = json.dumps(candidate, separators=(",", ":")).encode()
    with pytest.raises(SignedLibraryIndexRejected):
        verify_signed_library_index(raw, **kwargs)


def test_signed_index_rejects_wrong_independent_key(signed_catalog):
    _env, sign, kwargs = signed_catalog
    wrong = {**kwargs, "expected_publisher_key_sha256": "f" * 64}
    with pytest.raises(SignedLibraryIndexRejected, match="root differs"):
        verify_signed_library_index(sign(), **wrong)


@pytest.mark.parametrize("changed", [
    {"expected_target_platform_id": "other-recipient"},
    {"expected_source_platform_id": "other-primary"},
    {"expected_catalog_generation": 4},
    {"minimum_catalog_revision": 8},
])
def test_signed_index_rejects_wrong_audience_and_epoch(signed_catalog, changed):
    _env, sign, kwargs = signed_catalog
    with pytest.raises(SignedLibraryIndexRejected, match="mismatch"):
        verify_signed_library_index(sign(), **{**kwargs, **changed})


def test_signed_index_rejects_expired_and_revoked(signed_catalog):
    _env, sign, kwargs = signed_catalog
    with pytest.raises(SignedLibraryIndexRejected, match="stale"):
        verify_signed_library_index(
            sign(), **{**kwargs, "now": kwargs["now"] + timedelta(minutes=3)},
        )
    with pytest.raises(SignedLibraryIndexRejected, match="revoked"):
        verify_signed_library_index(
            sign(), **{**kwargs, "publisher_key_current": lambda _: False},
        )


def test_signed_index_rejects_duplicate_properties(signed_catalog):
    _env, sign, kwargs = signed_catalog
    raw = sign().decode("utf-8").replace(
        '"schema":', '"schema":"aegis.library.publisher-index.v1","schema":', 1,
    ).encode("utf-8")
    with pytest.raises(SignedLibraryIndexRejected, match="duplicate"):
        verify_signed_library_index(raw, **kwargs)


def test_signed_index_rejects_unsigned_catalog_edits(signed_catalog):
    envelope, sign, kwargs = signed_catalog
    malicious = {**envelope, "catalog": {**envelope["catalog"], "items": [
        {"artifact_id": "fabricated"},
    ]}}
    # Reuse original signature despite mutating the index.
    signed = json.loads(sign())
    signed["catalog"] = malicious["catalog"]
    with pytest.raises(SignedLibraryIndexRejected, match="signature"):
        verify_signed_library_index(
            json.dumps(signed, separators=(",", ":")).encode("utf-8"), **kwargs,
        )



def test_signed_but_expired_inner_catalog_refused(signed_catalog):
    env, sign, kwargs = signed_catalog
    env["catalog"]["catalog_fresh_until"] = (
        kwargs["now"] - timedelta(seconds=1)
    ).isoformat()
    with pytest.raises(SignedLibraryIndexRejected, match="catalog content"):
        verify_signed_library_index(sign(), **kwargs)
