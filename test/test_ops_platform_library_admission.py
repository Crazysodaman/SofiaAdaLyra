"""D028-02 internal-only signed Core-free cache vs B1 installed evidence.

No network, Hub, owner-secret transfer, real Core or native service. Fixtures
use disposable signed releases and the existing SAFE approval verifier.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import pytest

from sofia.platform.ops.platform_install import OfflineArtifactCache
from sofia.platform.ops.platform_installation import PlatformInstallationStore
from sofia.platform.ops.platform_library_admission import (
    LIBRARY_CACHE_ADMIT, preview_signed_seed_cache,
    admit_signed_seed_asset_with_owner_proof,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_ops_platform_installer_bundle import reviewed

pytestmark = [pytest.mark.pkg_ops, pytest.mark.skipif(
    os.name == "nt", reason="Debian synthetic signer/test native host fixture",
)]


@pytest.fixture
def context(reviewed, tmp_path, canonical_state_path, monkeypatch):
    import sofia.platform.ops.platform_library_admission as lib
    builder, root, manifest, params = reviewed
    monkeypatch.setattr(
        lib, "host_release_target",
        lambda: PlatformReleaseTarget.DEBIAN12_X86_64,
    )
    cache = OfflineArtifactCache(tmp_path / "library-cache", max_bytes=64 * 1024**2)
    store = PlatformInstallationStore(tmp_path / "installer.db")
    asset = next(item for item in manifest.assets if item.kind == "sdk")
    kwargs = dict(
        bundle_root=root, cache=cache, store=store,
        trusted_public_key=params["trusted_public_key"],
        trusted_key_sha256=params["trusted_key_sha256"],
        trusted_signer_key_id=params["trusted_signer_key_id"],
        expected_source_sha=params["expected_source_sha"],
        expected_target=params["expected_target"],
        minimum_revision=params["minimum_revision"],
        requested_asset_sha256=asset.reference.sha256,
    )
    return kwargs, canonical_state_path


def test_signed_seed_cache_preview_keeps_download_install_active_separate(context):
    args, state = context
    plan = preview_signed_seed_cache(**args, require_local_host=True)
    assert plan["schema"] == "aegis.platform.library.local-cache-review.v1"
    assert plan["cache_state"] == "MISSING"
    assert plan["signed_release_verified"] is True
    assert plan["installed"] is None
    assert plan["active"] is None
    assert plan["active_observation"] == "NOT_OBSERVED"
    assert plan["internet_enabled"] is False
    assert plan["current_owner_authorized"] is False
    assert plan["acquisition_executed"] is False
    assert plan["install_executed"] is False
    assert plan["core_activated"] is False
    assert args["store"].history() == []


def test_cache_admission_refuses_missing_owner_approval(context):
    args, state = context
    with pytest.raises((PermissionError, ValueError)):
        admit_signed_seed_asset_with_owner_proof(
            **args, canonical_safe_state=state, approval_id="",
        )
    with pytest.raises(PermissionError):
        admit_signed_seed_asset_with_owner_proof(
            **args, canonical_safe_state=state, approval_id="not-a-real-grant",
        )
    assert args["store"].history() == []


def test_one_use_safe_approved_cache_does_not_install_or_activate(context):
    args, state = context
    plan = preview_signed_seed_cache(**args)
    now = datetime.now(timezone.utc)
    params = dict(
        release_id=plan["release_id"], manifest_sha256=plan["manifest_sha256"],
        asset_sha256=plan["artifact_digest"],
        asset_size_bytes=plan["artifact_size_bytes"],
        target=args["expected_target"].value, source="OFFLINE_MEDIA",
        state=str(state.absolute()),
        cache_root=str(args["cache"].root),
        b1_receipts=str(args["store"].path),
    )
    approval = ExecutionApproval(
        approval_id="approval:d028-b-cache-admit",
        capability=LIBRARY_CACHE_ADMIT,
        request_fingerprint=execution_fingerprint(LIBRARY_CACHE_ADMIT, params),
        approved_by="person:sparks",
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(state), approval)
    outcome = admit_signed_seed_asset_with_owner_proof(
        **args, canonical_safe_state=state,
        approval_id=approval.approval_id, now=now,
    )
    assert outcome["cache_state"] == "CACHED_VERIFIED"
    assert outcome["acquisition_executed"] is True
    assert outcome["owner_proof_consumed"] is True
    assert outcome["install_executed"] is False
    assert outcome["active"] is None
    assert args["store"].history() == []
    observed = preview_signed_seed_cache(**args)
    assert observed["cache_state"] == "CACHED_VERIFIED"
    assert observed["installed"] is None
    assert observed["active"] is None
    with pytest.raises(PermissionError):
        admit_signed_seed_asset_with_owner_proof(
            **args, canonical_safe_state=state,
            approval_id=approval.approval_id, now=now + timedelta(seconds=1),
        )


def test_wrong_signed_asset_digest_cannot_be_admitted(context):
    args, state = context
    with pytest.raises(PlatformReleaseRejected, match="uniquely"):
        preview_signed_seed_cache(**{**args, "requested_asset_sha256": "f" * 64})
    assert args["store"].history() == []


def test_no_hub_can_claim_active_install_from_cache(context):
    args, state = context
    source = preview_signed_seed_cache(**args)
    assert source["source"] == "OFFLINE_MEDIA"
    assert source["installed"] is None
    assert source["active"] is None
    assert "Hub" not in str(source)


def test_operator_stop_denies_artifact_cache_write(context, monkeypatch):
    import sofia.platform.ops.platform_library_admission as module
    from types import SimpleNamespace
    args, state = context
    monkeypatch.setattr(
        module.OperatorStopStore, "current",
        lambda self: SimpleNamespace(active=True),
    )
    with pytest.raises(PermissionError, match="STOP"):
        admit_signed_seed_asset_with_owner_proof(
            **args, canonical_safe_state=state, approval_id="some-grant",
        )
    assert args["store"].history() == []
