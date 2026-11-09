"""Private one-owner D028 signed-index end-to-end over the existing native IPC.

Uses real disposable Linux SO_PEERCRED, canonical Platform RUN lease, owner
WebAuthn-backed SAFE enrollment, publisher Ed25519 signature, SQLite-persisted
catalog and revocation. NOT real signed installation or live-host certification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys
from uuid import uuid4

import pytest

from sofia.platform.run.library_owner_trust import (
    ENROLL_CAPABILITY, REVOKE_CAPABILITY, OwnerLibraryTrustStore,
    enrollment_parameters, revocation_parameters,
)
from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, execution_fingerprint,
)
from sofia.platform.safe.permissions import PermissionStore
from test.library_fixture_support import make_signed_catalog_fixture
from test.owner_auth_fixture import (
    record_verified_owner_approval, grant_with_signed_owner,
)
from test.test_platform_service_session import provision

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


def _authenticated_owner_approval(store, capability, parameters):
    moment = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=capability,
        request_fingerprint=execution_fingerprint(capability, parameters),
        approved_by="person:sparks", approved_at=moment,
        expires_at=moment + timedelta(minutes=5),
    )
    record_verified_owner_approval(store.approvals, approval)
    return approval.approval_id


def _query(endpoint, payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(endpoint)
        client.sendall(payload + b"\n")
        received = bytearray()
        while not received.endswith(b"\n"):
            block = client.recv(4096)
            if not block:
                return bytes(received)
            received.extend(block)
            if len(received) > 32768:
                raise AssertionError("unbounded native Library response")
        return bytes(received).strip()


def _catalog_request(platform_id, generation):
    now = datetime.now(timezone.utc)
    return json.dumps({
        "schema": "aegis.platform.library.request.v1",
        "protocol": "1.0",
        "request_id": "request:single-owner-host",
        "correlation_id": "correlation:single-owner-host",
        "operation": "library.catalog.snapshot.v1",
        "target_platform_id": platform_id,
        "expected_generation": generation,
        "expected_revision": 7,
        "idempotency_key": None,
        "created_at": (now - timedelta(seconds=1)).isoformat(),
        "deadline": (now + timedelta(seconds=15)).isoformat(),
        "parameters": {"limit": 32, "cursor": None, "kinds": []},
    }, separators=(",", ":"), sort_keys=True).encode()


@pytest.mark.skipif(not LINUX, reason="requires real Linux AF_UNIX peer credentials")
def test_single_owner_enrolls_publisher_and_native_service_reads_sqlite_index(tmp_path):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    trust = OwnerLibraryTrustStore(state, platform_id=platform_id)
    envelope, sign, keys = make_signed_catalog_fixture()
    now = datetime.now(timezone.utc)
    envelope["issued_at"] = (now - timedelta(seconds=2)).isoformat()
    envelope["expires_at"] = (now + timedelta(minutes=3)).isoformat()
    envelope["catalog"]["catalog_fresh_until"] = (
        now + timedelta(minutes=2)
    ).isoformat()
    envelope["catalog"]["source"]["last_observed_at"] = now.isoformat()
    envelope["target_platform_id"] = platform_id
    envelope["catalog"]["target_platform_id"] = platform_id
    exact = enrollment_parameters(
        state_path=state, platform_id=platform_id,
        source_platform_id="primary-library",
        public_key=keys["trusted_publisher_public_key"],
        catalog_generation=3, minimum_catalog_revision=7,
        previous_trust_generation=0,
    )
    authenticated = _authenticated_owner_approval(
        trust, ENROLL_CAPABILITY, exact,
    )
    grants = PermissionStore(state)
    with PlatformServiceSession(
        identity.home, state, platform_id, current.public_key_sha256,
    ) as service:
        status = service.status()
        endpoint = status["management_endpoint"]
        payload = _catalog_request(platform_id, status["generation"])
        # Stock fresh machine: even the local Linux owner cannot read an
        # unconfigured catalog or invent an approved publisher root.
        assert _query(endpoint, payload) == b""
        trust.enroll(
            source_platform_id="primary-library",
            public_key=keys["trusted_publisher_public_key"],
            catalog_generation=3, minimum_catalog_revision=7,
            approval_id=authenticated,
        )
        service.accept_installed_signed_library_catalog(sign())
        assert not trust.profile.exists()  # SQLite, no second catalog service
        # A signed catalog alone does not grant a local operator access.
        assert _query(endpoint, payload) == b""
        peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        grant_with_signed_owner(
            grants, "platform.library.read",
            scope={
                "platform_id": platform_id, "peer": peer,
                "operation": "library.catalog.snapshot.v1",
            },
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        response = json.loads(_query(endpoint, payload))
        assert response["outcome"] == "OK"
        assert response["data"]["source"]["source_id"] == "primary-library"
        assert response["data"]["catalog_revision"] == 7
        assert "installed" not in response["data"]
        pin = trust.current()
        revoke_id = _authenticated_owner_approval(
            trust, REVOKE_CAPABILITY,
            revocation_parameters(state_path=state, pin=pin),
        )
        trust.revoke(approval_id=revoke_id)
        assert _query(endpoint, _catalog_request(
            platform_id, status["generation"],
        )) == b""
        assert trust() is None
    assert trust.audit.verify() == (True, None)
