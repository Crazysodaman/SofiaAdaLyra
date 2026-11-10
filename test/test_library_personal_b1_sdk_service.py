"""D028 installed single-owner SDK acquisition selects the REAL B1 verifier.

The service wrapper is tested on one disposable canonical RUN session. A
captured executor deliberately avoids network, external host installation and
production SAFE grant effects; peer and one-use B1 approval tests live in
their separate original-repository integration suites.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from sofia.platform.ops.library_chunk_receiver import (
    ChunkedArtifactReceiver, ChunkTransferRejected,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache
from sofia.platform.run.platform_service import PlatformServiceSession
from test.test_library_b1_sdk_publisher import installed_sdk
from test.test_platform_service_session import provision


@pytest.fixture
def service_review(tmp_path, installed_sdk, monkeypatch):
    manifest, signer, signed_wheel, transfer, b1_store, args, authority = installed_sdk
    home = tmp_path / "installed-host"
    home.mkdir()
    identity, current, state = provision(home)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        # Service's target/epoch must be authentic even in this source test.
        transfer = replace(
            transfer, target_platform_id=current.identity.canonical_uuid,
            generation=service.status()["generation"],
        )
        captured = []
        def observe_without_network(**kwargs):
            captured.append(kwargs)
            artifact = kwargs["verify_independent_package"](
                kwargs["transfer"], signed_wheel,
            )
            assert artifact.signature_verified is True
            assert artifact.signer_key_id == "test-release"
            assert kwargs["package_signer_current"]("test-release") is True
            return {
                "schema": "aegis.platform.library.test-captured-sdk.v1",
                "cache_state": "CACHED_VERIFIED",
                "installed": None, "active": None,
                "install_executed": False,
            }
        monkeypatch.setattr(
            service, "acquire_owner_approved_library_asset",
            observe_without_network,
        )
        settings = dict(
            approval_id="owner-test-only-proof",
            transfer=transfer,
            expected_artifact_id=manifest.release_id,
            receiver=ChunkedArtifactReceiver(
                tmp_path / "quarantine", max_bytes=128 * 1024**2,
            ),
            cache=OfflineArtifactCache(
                tmp_path / "B1-cache", max_bytes=128 * 1024**2,
            ),
            open_enrolled_tls=lambda: (_ for _ in ()).throw(
                AssertionError("no external network in this unit test")
            ),
            enrolled_source_certificate_sha256="a" * 64,
            signed_b1_sdk_envelope=args["signed_envelope"],
            b1_verifier=args["verifier"],
            b1_installation=b1_store,
            expected_source_sha=args["expected_source_sha"],
            expected_target=args["expected_target"],
            trusted_signer_key_id=args["trusted_signer_key_id"],
            signer_current=args["signer_current"],
        )
        yield service, settings, captured, authority, signed_wheel


def test_service_selects_real_b1_signed_sdk_without_fabricating_install(service_review):
    service, config, captured, authority, signed_wheel = service_review
    result = service.acquire_owner_approved_library_sdk(**config)
    assert result["cache_state"] == "CACHED_VERIFIED"
    assert result["installed"] is None and result["active"] is None
    assert len(captured) == 1
    assert captured[0]["approval_id"] == "owner-test-only-proof"
    assert captured[0]["verify_independent_package"](
        config["transfer"], signed_wheel,
    ).sha256 == config["transfer"].content_sha256


def test_service_refuses_wrong_signed_manifest_before_effect(service_review):
    service, config, captured, authority, signed_wheel = service_review
    config["transfer"] = replace(
        config["transfer"], manifest_sha256="f" * 64,
    )
    with pytest.raises(ChunkTransferRejected, match="signed B1 manifest"):
        service.acquire_owner_approved_library_sdk(**config)
    assert captured == []


def test_service_refuses_wrong_sdk_release_identity_before_effect(service_review):
    service, config, captured, authority, signed_wheel = service_review
    config["expected_artifact_id"] = "another-signed-release"
    with pytest.raises(ChunkTransferRejected, match="release differs"):
        service.acquire_owner_approved_library_sdk(**config)
    assert captured == []


def test_service_refuses_revoked_b1_package_signer_before_effect(service_review):
    service, config, captured, authority, signed_wheel = service_review
    authority["current"] = False
    with pytest.raises(ChunkTransferRejected, match="revoked"):
        service.acquire_owner_approved_library_sdk(**config)
    assert captured == []


def test_service_does_not_treat_a_model_or_core_as_sdk(service_review):
    service, config, captured, authority, signed_wheel = service_review
    config["transfer"] = replace(config["transfer"], artifact_kind="model")
    with pytest.raises(ChunkTransferRejected, match="dedicated signed B1 SDK"):
        service.acquire_owner_approved_library_sdk(**config)
    assert captured == []
