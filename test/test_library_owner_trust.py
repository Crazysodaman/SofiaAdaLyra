"""D028 private one-owner signing-root enrollment and live service proof.

Real canonical SAFE approval and audit stores with disposable WebAuthn keys,
not production signing certificates or a signed installed release. Nothing
here starts a Hub, enrolls a TLS peer or installs any package.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.run.library_owner_trust import (
    ENROLL_CAPABILITY, REVOKE_CAPABILITY, OwnerLibraryTrustDenied,
    OwnerLibraryTrustStore, enrollment_parameters, revocation_parameters,
)
from sofia.platform.state.local_store import LocalStateUnavailable
from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.ops.library_signed_index import SignedLibraryIndexRejected
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, execution_fingerprint,
)
from test.library_fixture_support import make_signed_catalog_fixture
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_service_session import provision


def _approve(store, capability, params):
    now = store._now()
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=capability,
        request_fingerprint=execution_fingerprint(capability, params),
        approved_by="person:sparks", approved_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    record_verified_owner_approval(store.approvals, approval)
    return approval.approval_id


@pytest.fixture
def owner(tmp_path):
    identity, current, state = provision(tmp_path)
    env, sign, keys = make_signed_catalog_fixture()
    now = datetime.now(timezone.utc)
    env["issued_at"] = (now - timedelta(seconds=2)).isoformat()
    env["expires_at"] = (now + timedelta(minutes=3)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=2)
    ).isoformat()
    env["catalog"]["source"]["last_observed_at"] = now.isoformat()
    env["target_platform_id"] = current.identity.canonical_uuid
    env["catalog"]["target_platform_id"] = current.identity.canonical_uuid
    root = OwnerLibraryTrustStore(
        state, platform_id=current.identity.canonical_uuid,
        clock=lambda: now,
    )
    return identity, current, state, root, env, sign, keys, now


def _enroll(root, keys, *, epoch=3, floor=7, previous=0, source="primary-library"):
    params = enrollment_parameters(
        state_path=root.path, platform_id=root.platform_id,
        source_platform_id=source,
        public_key=keys["trusted_publisher_public_key"],
        catalog_generation=epoch, minimum_catalog_revision=floor,
        previous_trust_generation=previous,
    )
    approval = _approve(root, ENROLL_CAPABILITY, params)
    return root.enroll(
        source_platform_id=source,
        public_key=keys["trusted_publisher_public_key"],
        catalog_generation=epoch, minimum_catalog_revision=floor,
        approval_id=approval,
    ), approval


def test_unenrolled_platform_is_private_and_unavailable_not_tofu(owner):
    identity, current, state, root, env, sign, keys, now = owner
    assert root.current() is None
    assert root() is None
    with pytest.raises(PermissionError):
        root.enroll(
            source_platform_id="primary-library",
            public_key=keys["trusted_publisher_public_key"],
            catalog_generation=3, minimum_catalog_revision=7,
            approval_id="fabricated-owner-proof",
        )
    assert root.current() is None
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as session:
        # The stock service can load its own authenticated owner root once
        # enrolled. With no root it MUST NOT trust a discovered LAN publisher.
        assert session._installed_signed_catalog() is None
        assert session.status()["operator_stop"] is False


def test_owner_enrolls_once_then_existing_service_reads_publisher_signed_index(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, approval = _enroll(root, keys)
    assert pin.active and pin.trust_generation == 1
    assert pin.public_key_sha256 == keys["expected_publisher_key_sha256"]
    assert root.publisher_current(pin.public_key_sha256, 1) is True
    # Profile only stores signed bytes + public key. It has NO authority to
    # choose a trusted key or grant the current operator access.
    root.profile.write_text(json.dumps({
        "schema": "aegis.platform.library.installed-catalog-profile.v1",
        "signed_index_b64": b64encode(sign()).decode(),
        "publisher_public_key_b64": b64encode(
            keys["trusted_publisher_public_key"]
        ).decode(),
    }, sort_keys=True), encoding="utf-8")
    root.profile.chmod(0o600)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        provider = service._installed_signed_catalog
        assert isinstance(provider, OwnerLibraryTrustStore)
        index = provider()
        assert index.expected_source_platform_id == "primary-library"
        assert index.expected_catalog_generation == 3
        assert sha256(index.trusted_publisher_public_key).hexdigest() == pin.public_key_sha256
        assert service.status()["management_listening"] is True
        # A second enrollment cannot rotate trust without owner revocation.
        with pytest.raises(OwnerLibraryTrustDenied, match="revoke current"):
            root.enroll(
                source_platform_id="primary-library", public_key=pin.public_key,
                catalog_generation=4, minimum_catalog_revision=8,
                approval_id="not-a-real-proof",
            )


def test_owner_revocation_is_immediate_and_one_use_proof_cannot_replay(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, approval = _enroll(root, keys)
    params = revocation_parameters(state_path=root.path, pin=pin)
    revoked_id = _approve(root, REVOKE_CAPABILITY, params)
    revoked = root.revoke(approval_id=revoked_id)
    assert not revoked.active
    assert revoked.trust_generation == 1
    assert root.publisher_current(pin.public_key_sha256, 1) is False
    assert root() is None
    with pytest.raises(OwnerLibraryTrustDenied, match="no active"):
        root.revoke(approval_id=revoked_id)
    assert root.audit.verify() == (True, None)


def test_owner_rotation_needs_new_epoch_and_never_downgrades_revision(owner):
    identity, current, state, root, env, sign, keys, now = owner
    old, approval = _enroll(root, keys)
    revoke = _approve(root, REVOKE_CAPABILITY, revocation_parameters(
        state_path=root.path, pin=old,
    ))
    root.revoke(approval_id=revoke)
    for generation, floor in ((3, 8), (4, 6)):
        with pytest.raises(OwnerLibraryTrustDenied, match="advance"):
            root.enroll(
                source_platform_id="primary-library",
                public_key=keys["trusted_publisher_public_key"],
                catalog_generation=generation,
                minimum_catalog_revision=floor,
                approval_id="not-a-proof",
            )
    rotated, approval = _enroll(root, keys, epoch=4, floor=7, previous=1)
    assert rotated.trust_generation == 2
    assert root.publisher_current(rotated.public_key_sha256, 1) is False
    assert root.publisher_current(rotated.public_key_sha256, 2) is True


def test_foreign_platform_and_unapproved_key_change_are_rejected(owner, tmp_path):
    identity, current, state, root, env, sign, keys, now = owner
    with pytest.raises(OwnerLibraryTrustDenied, match="distinct"):
        enrollment_parameters(
            state_path=state, platform_id=root.platform_id,
            source_platform_id=root.platform_id,
            public_key=keys["trusted_publisher_public_key"],
            catalog_generation=3, minimum_catalog_revision=7,
            previous_trust_generation=0,
        )
    with pytest.raises((ValueError, OwnerLibraryTrustDenied, PermissionError, RuntimeError)):
        OwnerLibraryTrustStore(
            state, platform_id="different-installed-platform",
        )
    pin, _ = _enroll(root, keys)
    assert root.publisher_current("f" * 64, pin.trust_generation) is False
    assert root.publisher_current(pin.public_key_sha256, pin.trust_generation + 1) is False



def test_single_owner_can_store_signed_index_without_cloud_or_profile_file(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, _ = _enroll(root, keys)
    raw = sign()
    assert root.accept_signed_catalog(raw) == sha256(raw).hexdigest()
    assert not root.profile.exists()
    observed = root()
    assert observed.raw_signed_index == raw
    assert observed.trusted_publisher_public_key == pin.public_key
    assert observed.expected_source_platform_id == pin.source_platform_id
    assert observed.publisher_key_current(pin.public_key_sha256) is True
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as service:
        assert service._installed_signed_catalog().raw_signed_index == raw
        assert service.status()["operator_stop"] is False
    # Restart, not just a warm Python object: the signed page remains current.
    reloaded = OwnerLibraryTrustStore(state, platform_id=root.platform_id)
    assert reloaded().raw_signed_index == raw


def test_owner_signed_catalog_rejects_earlier_replayed_page_and_keeps_last(owner):
    identity, current, state, root, env, sign, keys, now = owner
    _enroll(root, keys)
    initial = sign()
    assert root.accept_signed_catalog(initial) == sha256(initial).hexdigest()
    assert root.accept_signed_catalog(initial) == sha256(initial).hexdigest()
    env["issued_at"] = (now - timedelta(seconds=1)).isoformat()
    env["expires_at"] = (now + timedelta(minutes=4)).isoformat()
    env["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=3)
    ).isoformat()
    newer = sign()
    assert root.accept_signed_catalog(newer) == sha256(newer).hexdigest()
    with pytest.raises(OwnerLibraryTrustDenied, match="replay"):
        root.accept_signed_catalog(initial)
    assert root().raw_signed_index == newer
    assert root.audit.verify() == (True, None)


def test_owner_signed_catalog_rejects_wrong_target_revocation_and_tamper(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, _ = _enroll(root, keys)
    env["target_platform_id"] = "other-platform"
    env["catalog"]["target_platform_id"] = "other-platform"
    with pytest.raises(SignedLibraryIndexRejected, match="mismatch"):
        root.accept_signed_catalog(sign())
    env["target_platform_id"] = root.platform_id
    env["catalog"]["target_platform_id"] = root.platform_id
    raw = sign()
    root.accept_signed_catalog(raw)
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE platform_library_owner_index SET signed_index=? "
            "WHERE singleton=1", (b"forged-publisher-bytes",),
        )
    with pytest.raises(OwnerLibraryTrustDenied, match="changed"):
        root()
    # Repair signed snapshot only by an owner-pinned publisher, no self-trust.
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE platform_library_owner_index SET signed_index=? "
            "WHERE singleton=1", (raw,),
        )
    revocation_id = _approve(root, REVOKE_CAPABILITY, revocation_parameters(
        state_path=root.path, pin=pin,
    ))
    root.revoke(approval_id=revocation_id)
    assert root() is None
    with pytest.raises(OwnerLibraryTrustDenied, match="current owner"):
        root.accept_signed_catalog(raw)


def test_enrollment_is_exactly_one_current_owner_not_a_blanket_fleet_root(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, _ = _enroll(root, keys)
    assert root.current().source_platform_id == "primary-library"
    other_host, other_identity, other_state = None, None, None
    with pytest.raises((
        ValueError, OwnerLibraryTrustDenied, PermissionError,
        LocalStateUnavailable,
    )):
        OwnerLibraryTrustStore(
            state, platform_id="other-platform",
        )
    assert root.publisher_current(pin.public_key_sha256, 9999) is False



def test_stop_blocks_signed_catalog_reads_and_updates_but_allows_owner_revocation(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, _ = _enroll(root, keys)
    signed = sign()
    root.accept_signed_catalog(signed)
    root.stop.set(
        active=True, updated_by="Sparks",
        reason="single-owner emergency Platform STOP",
        at=now,
    )
    assert root() is None
    assert root.publisher_current(pin.public_key_sha256, 1) is False
    with pytest.raises(OwnerLibraryTrustDenied, match="STOP-free"):
        root.accept_signed_catalog(signed)
    # Revocation during STOP is an important emergency recovery operation,
    # and still requires exact separately authenticated owner proof.
    approval = _approve(root, REVOKE_CAPABILITY, revocation_parameters(
        state_path=state, pin=pin,
    ))
    assert root.revoke(approval_id=approval).active is False
    assert root() is None
    assert root.audit.verify() == (True, None)


def test_owner_snapshot_expiry_fails_closed_after_clock_advance(owner):
    identity, current, state, root, env, sign, keys, now = owner
    _enroll(root, keys)
    signed = sign()
    root.accept_signed_catalog(signed)
    assert root().raw_signed_index == signed
    root.clock = lambda: now + timedelta(minutes=6)
    with pytest.raises(SignedLibraryIndexRejected, match="stale"):
        root()



def test_tampered_safe_audit_chain_never_accepts_owner_trust_mutations(owner):
    identity, current, state, root, env, sign, keys, now = owner
    pin, _ = _enroll(root, keys)
    root.accept_signed_catalog(sign())
    with sqlite3.connect(state) as db:
        event = db.execute(
            "SELECT event_id FROM safe_audit_event ORDER BY sequence LIMIT 1"
        ).fetchone()
        assert event is not None
        db.execute(
            "UPDATE safe_audit_event SET payload_json=? WHERE event_id=?",
            ('{"forged":"audit"}', event[0]),
        )
    assert root.audit.verify()[0] is False
    with pytest.raises(OwnerLibraryTrustDenied, match="audit chain"):
        root.accept_signed_catalog(sign())
    with pytest.raises(OwnerLibraryTrustDenied, match="audit chain"):
        root.revoke(approval_id="not-even-an-owner-proof")
    with pytest.raises(OwnerLibraryTrustDenied, match="audit chain"):
        root.enroll(
            source_platform_id="primary-library",
            public_key=keys["trusted_publisher_public_key"],
            catalog_generation=4, minimum_catalog_revision=8,
            approval_id="not-even-an-owner-proof",
        )
