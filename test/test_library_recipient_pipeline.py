"""D028 state-separation integration contract, isolated from real host effects."""
from __future__ import annotations

import pytest
from datetime import timedelta

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.library_recipient_pipeline import (
    acquire_selected_signed_platform_asset, acquire_from_independently_signed_index,
)
from sofia.platform.ops.platform_install import (OfflineArtifactCache, PlatformArtifact, PlatformKind)
from test.test_library_tls_chunk_transport import _transfer
from test.library_fixture_support import make_signed_offer_fixture


@pytest.fixture
def signed_offer_fixture():
    return make_signed_offer_fixture()


@pytest.fixture
def environment(tmp_path, monkeypatch):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    data = b"signed-public-sdk" * 1200
    original = _transfer(data)
    transfer = PinnedChunkTransfer(
        source_platform_id=original.source_platform_id,
        target_platform_id=original.target_platform_id,
        content_sha256=original.content_sha256,
        size_bytes=len(data), generation=original.generation,
        manifest_sha256=original.manifest_sha256,
        catalog_revision=original.catalog_revision, artifact_kind="sdk",
        license_distribution="permitted", data_class="public",
    )
    receiver = ChunkedArtifactReceiver(tmp_path / "quarantine", max_bytes=100000)
    cache = OfflineArtifactCache(tmp_path / "B1-cache", max_bytes=100000)
    calls = []
    def simulated_fetch(**kwargs):
        calls.append(("fetch", kwargs["start_offset"]))
        return kwargs["start_offset"] + min(kwargs["chunk_bytes"] * kwargs["max_chunks"], len(data) - kwargs["start_offset"])
    def simulated_admit(**kwargs):
        calls.append(("admit", kwargs["transfer"].content_sha256))
        return dict(cache_state="CACHED_VERIFIED", owner_proof_consumed=True,
                    install_executed=False, installed=None, active=None)
    monkeypatch.setattr(pipeline, "fetch_resumable_chunks", simulated_fetch)
    monkeypatch.setattr(pipeline, "admit_signed_transferred_asset", simulated_admit)
    args = dict(
        transfer=transfer, receiver=receiver, cache=cache,
        open_enrolled_tls=lambda: None,
        expected_peer_certificate_sha256="1" * 64,
        authorize_peer=lambda *_: True,
        publisher_current=lambda _: True,
        current_host_admit=lambda _: True,
        verify_independent_publisher=lambda *_: None,
        canonical_safe_state=tmp_path / "canonical-safe.db",
        approval_id="current-owner-proof",
        start_offset=0, chunk_bytes=2048, max_chunks=1,
    )
    return args, calls, data


def test_partial_recipient_fetch_does_not_claim_install_or_signature(environment):
    args, calls, data = environment
    result = acquire_selected_signed_platform_asset(**args)
    assert result["received_bytes"] == 2048
    assert result["verified_bytes"] == 0
    assert result["cache_state"] == "RECEIVING"
    assert result["owner_proof_consumed"] is False
    assert result["installed"] is None and result["active"] is None
    assert calls == [("fetch", 0)]


def test_full_recipient_fetch_invokes_exact_signed_handoff(environment):
    args, calls, data = environment
    args["max_chunks"] = 100
    result = acquire_selected_signed_platform_asset(**args)
    assert result["received_bytes"] == len(data)
    assert result["verified_bytes"] == len(data)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["owner_proof_consumed"] is True
    assert result["install_executed"] is False
    assert calls == [("fetch", 0), ("admit", args["transfer"].content_sha256)]


def test_current_recipient_denial_prevents_network_and_cache(environment):
    args, calls, _ = environment
    args["current_host_admit"] = lambda _: False
    with pytest.raises(PermissionError, match="SAFE"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []


def test_publisher_revocation_denies_before_network_and_cache(environment):
    args, calls, _ = environment
    args["publisher_current"] = lambda _: False
    with pytest.raises(ChunkTransferRejected, match="publisher"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []


def test_wrong_artifact_kind_uses_dedicated_pipeline(environment):
    args, calls, _ = environment
    prior = args["transfer"]
    args["transfer"] = PinnedChunkTransfer(
        source_platform_id=prior.source_platform_id,
        target_platform_id=prior.target_platform_id,
        content_sha256=prior.content_sha256, size_bytes=prior.size_bytes,
        generation=prior.generation, manifest_sha256=prior.manifest_sha256,
        catalog_revision=prior.catalog_revision, artifact_kind="module",
        license_distribution="permitted", data_class="public",
    )
    with pytest.raises(ChunkTransferRejected, match="separate module"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []



def test_signed_index_wrapper_binds_real_catalog_key_and_selected_transfer(
    signed_offer_fixture, environment, monkeypatch, tmp_path,
):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    _env, _sign, signed_args = signed_offer_fixture
    original_args, _calls, _raw = environment
    captured = []
    def source_pipeline(**kwargs):
        captured.append(kwargs)
        assert kwargs["transfer"] == signed_args["transfer"]
        assert kwargs["publisher_current"](signed_args["transfer"]) is True
        assert kwargs["verify_independent_publisher"] is not None
        return {
            "cache_state": "RECEIVING", "received_bytes": 128,
            "verified_bytes": 0, "install_executed": False,
            "installed": None, "active": None,
        }
    monkeypatch.setattr(pipeline, "acquire_selected_signed_platform_asset", source_pipeline)
    result = acquire_from_independently_signed_index(
        **{**original_args,
           "transfer": signed_args["transfer"],
           "raw_signed_index": signed_args["raw_signed_index"],
           "expected_artifact_id": signed_args["expected_artifact_id"],
           "trusted_publisher_public_key": signed_args["trusted_publisher_public_key"],
           "expected_publisher_key_sha256": signed_args["expected_publisher_key_sha256"],
           "expected_catalog_generation": signed_args["expected_catalog_generation"],
           "publisher_key_current": lambda _: True,
           "now": signed_args["now"], "current_time": lambda: signed_args["now"]},
    )
    assert result["selected_artifact_id"] == "sdk.release.1"
    assert len(result["signed_index_sha256"]) == 64
    assert len(captured) == 1
    assert result["verified_bytes"] == 0


def test_signed_index_wrapper_refuses_untrusted_index_before_any_transfer(
    signed_offer_fixture, environment, monkeypatch,
):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    _env, _sign, signed_args = signed_offer_fixture
    original_args, _calls, _raw = environment
    executed = []
    monkeypatch.setattr(
        pipeline, "acquire_selected_signed_platform_asset",
        lambda **_: executed.append(True),
    )
    from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
    with pytest.raises(SignedLibraryIndexRejected):
        acquire_from_independently_signed_index(
            **{**original_args,
               "transfer": signed_args["transfer"],
               "raw_signed_index": signed_args["raw_signed_index"],
               "expected_artifact_id": signed_args["expected_artifact_id"],
               "trusted_publisher_public_key": signed_args["trusted_publisher_public_key"],
               "expected_publisher_key_sha256": "f" * 64,
               "expected_catalog_generation": signed_args["expected_catalog_generation"],
               "publisher_key_current": lambda _: True,
               "now": signed_args["now"], "current_time": lambda: signed_args["now"]},
        )
    assert executed == []


def test_signed_index_wrapper_rejects_package_signer_mismatch(
    signed_offer_fixture, environment, monkeypatch,
):
    import sofia.platform.ops.library_recipient_pipeline as pipeline
    _env, _sign, signed_args = signed_offer_fixture
    original_args, _calls, _raw = environment
    def source_pipeline(**kwargs):
        transfer = kwargs["transfer"]
        kwargs["verify_independent_publisher"](
            transfer, kwargs["canonical_safe_state"],
        )
        return {}
    def independent_verifier(transfer, path):
        return PlatformArtifact(
            artifact_id="sdk.release.1", version="1.0",
            platform=PlatformKind.LINUX, architecture="x86_64",
            sha256=transfer.content_sha256,
            signer_key_id="different-untrusted-package-signer",
            signature_verified=True, source="synthetic-test-archive",
        )
    monkeypatch.setattr(pipeline, "acquire_selected_signed_platform_asset", source_pipeline)
    with pytest.raises(ChunkTransferRejected, match="differs"):
        acquire_from_independently_signed_index(
            **{**original_args,
               "transfer": signed_args["transfer"],
               "raw_signed_index": signed_args["raw_signed_index"],
               "expected_artifact_id": signed_args["expected_artifact_id"],
               "trusted_publisher_public_key": signed_args["trusted_publisher_public_key"],
               "expected_publisher_key_sha256": signed_args["expected_publisher_key_sha256"],
               "expected_catalog_generation": signed_args["expected_catalog_generation"],
               "publisher_key_current": lambda _: True,
               "verify_independent_publisher": independent_verifier,
               "now": signed_args["now"], "current_time": lambda: signed_args["now"]},
        )



def test_expired_signed_index_denied_at_runtime_before_fetch(
    signed_offer_fixture, environment,
):
    _env, _sign, signed_args = signed_offer_fixture
    original_args, calls, _raw = environment
    with pytest.raises(ChunkTransferRejected, match="publisher"):
        acquire_from_independently_signed_index(
            **{**original_args,
               "transfer": signed_args["transfer"],
               "raw_signed_index": signed_args["raw_signed_index"],
               "expected_artifact_id": signed_args["expected_artifact_id"],
               "trusted_publisher_public_key": signed_args["trusted_publisher_public_key"],
               "expected_publisher_key_sha256": signed_args["expected_publisher_key_sha256"],
               "expected_catalog_generation": signed_args["expected_catalog_generation"],
               "publisher_key_current": lambda _: True,
               "now": signed_args["now"],
               "current_time": lambda: signed_args["now"] + timedelta(minutes=3)},
        )
    assert calls == []



def _prepare_complete_pending_import(args, data):
    """Real receiver CAS commit, but defer owner B1 approval."""
    from hashlib import sha256
    transfer = args["transfer"]
    receiver = args["receiver"]
    receiver.append_chunk(
        transfer, offset=0, chunk=data,
        chunk_sha256=sha256(data).hexdigest(),
        authorize=lambda _: True,
    )
    complete = receiver.finalize(
        transfer, authorize=lambda _: True, retain_scope=True,
    )
    assert complete.read_bytes() == data
    assert (receiver.incoming / (transfer.content_sha256 + ".scope")).is_file()
    return complete


@pytest.mark.parametrize("resume_cursor", ("zero", "complete"))
def test_completed_quarantine_retry_never_dials_peer(environment, resume_cursor):
    args, calls, data = environment
    complete = _prepare_complete_pending_import(args, data)
    args["open_enrolled_tls"] = lambda: (_ for _ in ()).throw(
        AssertionError("full signed CAS must NOT redownload")
    )
    args["start_offset"] = (
        0 if resume_cursor == "zero" else args["transfer"].size_bytes
    )
    result = acquire_selected_signed_platform_asset(**args)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["network_attempted"] is False
    assert result["reused_complete_quarantine"] is True
    assert result["received_bytes"] == len(data)
    assert result["verified_bytes"] == len(data)
    assert result["install_executed"] is False
    assert result["installed"] is None and result["active"] is None
    assert calls == [("admit", args["transfer"].content_sha256)]
    assert complete.read_bytes() == data


def test_completed_quarantine_retry_refuses_wrong_signed_scope_before_network(environment):
    from dataclasses import replace
    args, calls, data = environment
    complete = _prepare_complete_pending_import(args, data)
    args["transfer"] = replace(
        args["transfer"], manifest_sha256="f" * 64,
    )
    with pytest.raises(ChunkTransferRejected, match="scope"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []
    assert complete.read_bytes() == data


def test_completed_quarantine_retry_requires_current_owner_and_publisher(environment):
    args, calls, data = environment
    complete = _prepare_complete_pending_import(args, data)
    args["current_host_admit"] = lambda _: False
    with pytest.raises(PermissionError, match="SAFE"):
        acquire_selected_signed_platform_asset(**args)
    args["current_host_admit"] = lambda _: True
    args["publisher_current"] = lambda _: False
    with pytest.raises(ChunkTransferRejected, match="publisher"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []
    assert complete.read_bytes() == data


def test_completed_quarantine_retry_refuses_ambiguous_partial_offset(environment):
    args, calls, data = environment
    complete = _prepare_complete_pending_import(args, data)
    args["start_offset"] = 22
    with pytest.raises(ChunkTransferRejected, match="retry cursor"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []
    assert complete.read_bytes() == data



def test_unbound_completed_blob_never_triggers_retransfer_or_cache_approval(
    environment,
):
    args, calls, data = environment
    receiver = args["receiver"]
    pin = args["transfer"]
    complete = receiver.completed / pin.content_sha256
    complete.write_bytes(data)
    complete.chmod(0o600)
    # A previously completed object without its current exact signed scope
    # must not be silently adopted, redownloaded or promoted as B1 trust.
    with pytest.raises(ChunkTransferRejected, match="lacks exact signed"):
        acquire_selected_signed_platform_asset(**args)
    assert calls == []
    assert complete.read_bytes() == data
