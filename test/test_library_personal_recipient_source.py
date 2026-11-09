"""D028 source selection for a personal recipient uses own Platform SAFE DB.

This is an internal service wiring test, not a certified network transfer.
The stub is deliberately limited to checking the correct trust-source
injection; real HostedLibraryRecipient still enforces mTLS, per-chunk grants,
independently signed package verifier and one-use B1 cache admission.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.run.library_owner_trust import (
    OwnerLibraryTrustStore, ENROLL_CAPABILITY, enrollment_parameters,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, execution_fingerprint,
)
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_service_session import provision
from test.library_fixture_support import make_signed_catalog_fixture


def _owner_pin(trust, public):
    params = enrollment_parameters(
        state_path=trust.path, platform_id=trust.platform_id,
        source_platform_id="owner-primary-hub", public_key=public,
        catalog_generation=3, minimum_catalog_revision=7,
        previous_trust_generation=0,
    )
    now = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=ENROLL_CAPABILITY,
        request_fingerprint=execution_fingerprint(ENROLL_CAPABILITY, params),
        approved_by="person:sparks", approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(trust.approvals, approval)
    trust.enroll(
        source_platform_id="owner-primary-hub", public_key=public,
        catalog_generation=3, minimum_catalog_revision=7,
        approval_id=approval.approval_id,
    )


def test_installed_recipient_uses_owner_database_not_remote_signer_flags(tmp_path, monkeypatch):
    import sofia.platform.run.library_recipient_service as recipient
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    trust = OwnerLibraryTrustStore(state, platform_id=platform_id)
    doc, sign, keys = make_signed_catalog_fixture()
    now = datetime.now(timezone.utc)
    doc["source_platform_id"] = "owner-primary-hub"
    doc["catalog"]["source"]["source_id"] = "owner-primary-hub"
    doc["target_platform_id"] = platform_id
    doc["catalog"]["target_platform_id"] = platform_id
    doc["issued_at"] = (now - timedelta(seconds=2)).isoformat()
    doc["expires_at"] = (now + timedelta(minutes=3)).isoformat()
    doc["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=2)
    ).isoformat()
    doc["catalog"]["source"]["last_observed_at"] = now.isoformat()
    observed = []

    class ConfigurationProbe:
        def __init__(self, *, service, signed_catalog_source, **other):
            assert service.status()["platform_id"] == platform_id
            assert "trusted_publisher_public_key" not in other
            assert "expected_publisher_key_sha256" not in other
            observed.append(signed_catalog_source())
        def acquire(self, *, approval_id, start_offset, chunk_bytes, max_chunks):
            assert approval_id == "test-owner-proof-unused-by-probe"
            return {"result": "PROBE_ONLY", "install_executed": False}

    monkeypatch.setattr(recipient, "HostedLibraryRecipient", ConfigurationProbe)
    with PlatformServiceSession(
        identity.home, state, platform_id, current.public_key_sha256,
    ) as session:
        first = session.acquire_owner_approved_library_asset(
            approval_id="test-owner-proof-unused-by-probe",
        )
        assert first["install_executed"] is False
        assert observed == [None]
        _owner_pin(trust, keys["trusted_publisher_public_key"])
        trust.accept_signed_catalog(sign())
        second = session.acquire_owner_approved_library_asset(
            approval_id="test-owner-proof-unused-by-probe",
        )
        assert second["result"] == "PROBE_ONLY"
        assert observed[1].expected_source_platform_id == "owner-primary-hub"
        assert observed[1].expected_catalog_generation == 3
        assert observed[1].trusted_publisher_public_key == (
            keys["trusted_publisher_public_key"]
        )
    # No real peer read, cache mutation or install occurred in this stub test.
