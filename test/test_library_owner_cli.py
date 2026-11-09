"""One-owner headless Library CLI exercises real SAFE proof, no cloud daemon.

The exact action fingerprints are signed with disposable test-only owner
WebAuthn credentials. This is not production signing or installation GO.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from uuid import uuid4

import pytest

from sofia.platform.ops.library_owner_cli import main
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier,
)
from test.library_fixture_support import make_signed_catalog_fixture
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_service_session import provision


def _call(state, platform_id, *rest):
    return main([
        "--state", str(state), "--platform-id", platform_id, *rest,
    ])


def _authorize_preview(state, preview):
    instant = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()),
        capability=preview["capability"],
        request_fingerprint=preview["request_fingerprint"],
        approved_by="person:sparks",
        approved_at=instant,
        expires_at=instant + timedelta(minutes=5),
    )
    record_verified_owner_approval(
        ExecutionApprovalVerifier(state), approval,
    )
    return approval.approval_id


def test_single_owner_headless_enroll_signed_catalog_and_revoke(
    tmp_path, capsys,
):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    doc, sign, keys = make_signed_catalog_fixture()
    instant = datetime.now(timezone.utc)
    doc["issued_at"] = (instant - timedelta(seconds=2)).isoformat()
    doc["expires_at"] = (instant + timedelta(minutes=3)).isoformat()
    doc["catalog"]["catalog_fresh_until"] = (
        instant + timedelta(minutes=2)
    ).isoformat()
    doc["catalog"]["source"]["last_observed_at"] = instant.isoformat()
    doc["target_platform_id"] = platform_id
    doc["catalog"]["target_platform_id"] = platform_id
    key_path = tmp_path / "owner-approved-public-key.bin"
    key_path.write_bytes(keys["trusted_publisher_public_key"])
    key_path.chmod(0o600)
    raw_index = sign()
    catalog_path = tmp_path / "signed-current-index.json"
    catalog_path.write_bytes(raw_index)
    catalog_path.chmod(0o600)

    assert _call(state, platform_id, "status") == 0
    status = json.loads(capsys.readouterr().out)
    assert status["owner_mode"] == "SINGLE_OWNER_PRIVATE"
    assert status["publisher_state"] == "UNENROLLED"

    enroll_args = [
        "--source-platform-id", "primary-library",
        "--public-key", str(key_path), "--catalog-generation", "3",
        "--minimum-revision", "7",
    ]
    assert _call(state, platform_id, "prepare-enroll", *enroll_args) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["owner_approval_recorded"] is False
    assert preview["effect_executed"] is False
    assert preview["parameters"]["publisher_public_key_sha256"] == (
        keys["expected_publisher_key_sha256"]
    )

    # Missing auth is a denial, not a trust-on-first-use prompt.
    assert _call(
        state, platform_id, "enroll", *enroll_args,
        "--approval-id", "fabricated",
    ) == 2
    assert "refused" in capsys.readouterr().err

    authorized = _authorize_preview(state, preview)
    assert _call(
        state, platform_id, "enroll", *enroll_args,
        "--approval-id", authorized,
    ) == 0
    enrolled = json.loads(capsys.readouterr().out)
    assert enrolled["result"] == "OWNER_PUBLISHER_ENROLLED"
    assert enrolled["trust_generation"] == 1
    assert enrolled["install_executed"] is False

    assert _call(
        state, platform_id, "import-index", "--file", str(catalog_path),
    ) == 0
    admitted = json.loads(capsys.readouterr().out)
    assert admitted["result"] == "SIGNED_CATALOG_CACHED"
    assert admitted["signed_index_sha256"] == sha256(raw_index).hexdigest()
    assert admitted["core_activated"] is False

    assert _call(state, platform_id, "status") == 0
    latest = json.loads(capsys.readouterr().out)
    assert latest["publisher_state"] == "SIGNED_INDEX_CURRENT"
    assert latest["verified_catalog_revision"] == 7

    assert _call(state, platform_id, "prepare-revoke") == 0
    revocation_preview = json.loads(capsys.readouterr().out)
    revoke_approval = _authorize_preview(state, revocation_preview)
    assert _call(
        state, platform_id, "revoke", "--approval-id", revoke_approval,
    ) == 0
    final = json.loads(capsys.readouterr().out)
    assert final["result"] == "OWNER_PUBLISHER_REVOKED"

    assert _call(state, platform_id, "status") == 0
    result = json.loads(capsys.readouterr().out)
    assert result["publisher_state"] == "REVOKED"
    assert result["verified_catalog_revision"] is None

    # One-use enrollment approval must not resurrect the prior publisher.
    assert _call(
        state, platform_id, "enroll", *enroll_args,
        "--approval-id", authorized,
    ) == 2


@pytest.mark.skipif(os.name == "nt", reason="POSIX file redirect and link modes")
def test_owner_cli_denies_redirected_key_and_catalog_input(tmp_path, capsys):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    source = tmp_path / "owner-key"
    source.write_bytes(b"k" * 32)
    source.chmod(0o600)
    redirect = tmp_path / "untrusted-key-link"
    redirect.symlink_to(source)
    assert _call(
        state, platform_id, "prepare-enroll",
        "--source-platform-id", "primary-library",
        "--public-key", str(redirect),
        "--catalog-generation", "3", "--minimum-revision", "7",
    ) == 2
    assert "refused" in capsys.readouterr().err
    signed = tmp_path / "catalog"
    signed.write_bytes(b"untrusted-index")
    extra = tmp_path / "hardlinked-catalog"
    os.link(signed, extra)
    assert _call(
        state, platform_id, "import-index", "--file", str(signed),
    ) == 2
    assert "refused" in capsys.readouterr().err


def test_owner_cli_cannot_select_a_foreign_platform_identity(tmp_path, capsys):
    identity, current, state = provision(tmp_path)
    assert _call(state, "different-installed-platform", "status") == 2
    assert "refused" in capsys.readouterr().err
