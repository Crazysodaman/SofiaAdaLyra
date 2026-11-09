"""D028 signed index -> exact selected immutable transfer binding tests."""
from __future__ import annotations

from hashlib import sha256

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from sofia.platform.ops.library_signed_selection import verify_selected_signed_transfer
from test.library_fixture_support import make_signed_offer_fixture


@pytest.fixture
def signed_offer():
    return make_signed_offer_fixture()

def test_signed_selection_binds_immutable_bytes_and_recipient(signed_offer):
    _env, _sign, args = signed_offer
    selection = verify_selected_signed_transfer(**args)
    assert selection.transfer == args["transfer"]
    assert selection.artifact_id == "sdk.release.1"
    assert selection.signer_key_id == "independently-trusted-release-key"
    assert selection.still_matches()
    selection.index.catalog["items"][0]["size_bytes"] += 1
    assert not selection.still_matches()


def test_signed_selection_refuses_changed_content_digest(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"][0]["content_digest"] = "0" * 64
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="differs"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_refuses_redistribution_restricted_asset(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"][0]["distribution_allowed"] = False
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="differs"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_rejects_ambiguous_offer(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["items"].append(dict(env["catalog"]["items"][0]))
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="ambiguous"):
        verify_selected_signed_transfer(**args)


def test_signed_selection_rejects_expired_or_untrusted_index(signed_offer):
    _env, _sign, args = signed_offer
    with pytest.raises(SignedLibraryIndexRejected, match="revoked"):
        verify_selected_signed_transfer(
            **{**args, "publisher_key_current": lambda _: False},
        )


def test_signed_selection_rejects_wrong_owner_selected_id(signed_offer):
    env, sign, args = signed_offer
    env["catalog"]["source"]["source_id"] = "untrusted-sender"
    args["raw_signed_index"] = sign()
    with pytest.raises(ChunkTransferRejected, match="source"):
        verify_selected_signed_transfer(**args)
