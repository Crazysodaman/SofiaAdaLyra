"""D028 long-running private Hub needs fresh signed index without asset swap.

All keys are test-only; renewal is independent publisher signature validation,
not host enrollment or authorization of a new transfer.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkTransferRejected
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from sofia.platform.ops.library_signed_selection import verify_selected_signed_transfer
from sofia.platform.run.library_host_service import verify_renewed_serving_offer
from test.library_fixture_support import make_signed_offer_fixture


@pytest.fixture
def renewal():
    env, sign, params = make_signed_offer_fixture()
    original = verify_selected_signed_transfer(**params)
    current = params["now"] + timedelta(minutes=2)
    assert original.index.expires_at < current
    env["issued_at"] = (current - timedelta(seconds=1)).isoformat()
    env["expires_at"] = (current + timedelta(minutes=2)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (current + timedelta(minutes=1)).isoformat()
    env["catalog"]["source"]["last_observed_at"] = current.isoformat()
    options = {
        "original": original,
        "trusted_publisher_public_key": params["trusted_publisher_public_key"],
        "expected_publisher_key_sha256": params["expected_publisher_key_sha256"],
        "expected_catalog_generation": params["expected_catalog_generation"],
        "publisher_key_current": params["publisher_key_current"],
        "now": current,
    }
    return env, sign, options


def test_expired_old_index_can_refresh_only_same_signed_manifest_and_peer(renewal):
    env, sign, params = renewal
    renewed = verify_renewed_serving_offer(
        raw_signed_index=sign(), **params,
    )
    assert renewed.transfer == params["original"].transfer
    assert renewed.index.expires_at > params["now"]
    assert renewed.signer_key_id == params["original"].signer_key_id
    assert renewed.signature_receipt_ref == params["original"].signature_receipt_ref
    assert renewed.index.signed_index_sha256 != params["original"].index.signed_index_sha256


@pytest.mark.parametrize("field,changed", [
    ("signer_key_id", "other-signer"),
    ("signature_receipt_ref", "other-receipt"),
    ("version", "2.0"),
    ("artifact_id", "other-release"),
])
def test_validly_signed_renewal_cannot_swap_approved_package_identity(
    renewal, field, changed,
):
    env, sign, params = renewal
    env["catalog"]["items"][0][field] = changed
    with pytest.raises(ChunkTransferRejected):
        verify_renewed_serving_offer(
            raw_signed_index=sign(), **params,
        )


def test_validly_signed_renewal_cannot_switch_source_role(renewal):
    env, sign, params = renewal
    env["catalog"]["source"]["kind"] = "AUTHORIZED_PEER"
    with pytest.raises(ChunkTransferRejected, match="immutable signed Hub offer"):
        verify_renewed_serving_offer(raw_signed_index=sign(), **params)


def test_renewal_cannot_revive_revoked_publisher_key(renewal):
    env, sign, params = renewal
    with pytest.raises(SignedLibraryIndexRejected, match="revoked"):
        verify_renewed_serving_offer(
            raw_signed_index=sign(),
            **{**params, "publisher_key_current": lambda _: False},
        )


def test_stale_renewal_denied_even_if_old_signature_was_good(renewal):
    env, sign, params = renewal
    env["issued_at"] = (params["now"] - timedelta(minutes=10)).isoformat()
    env["expires_at"] = (params["now"] - timedelta(minutes=9)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (
        params["now"] - timedelta(minutes=9, seconds=20)
    ).isoformat()
    with pytest.raises(SignedLibraryIndexRejected, match="stale"):
        verify_renewed_serving_offer(
            raw_signed_index=sign(), **params,
        )


def test_renewal_fails_if_original_verified_catalog_was_mutated(renewal):
    env, sign, params = renewal
    params["original"].index.catalog["source"]["status"] = "STALE"
    with pytest.raises(ChunkTransferRejected, match="changed"):
        verify_renewed_serving_offer(
            raw_signed_index=sign(), **params,
        )
