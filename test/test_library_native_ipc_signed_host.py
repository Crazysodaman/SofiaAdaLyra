"""D028 real disposable AF_UNIX Platform service + owner-granted signed catalog.

This is an original-repository runnable test that uses a real Platform RUN
lease, installation identity, native SO_PEERCRED listener, current SAFE
owner-authenticated grant and a real synthetic Ed25519 signature.
It is NOT signed package deployment, Windows integration or production GO.
"""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys

import pytest

from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.run.library_installed_catalog import InstalledLibraryCatalogProvider
from sofia.platform.safe.permissions import PermissionStore
from test.library_fixture_support import make_signed_catalog_fixture
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
from test.test_platform_service_session import provision

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


def _request(platform_id, generation, *, revision=7):
    now = datetime.now(timezone.utc)
    return json.dumps({
        "schema": "aegis.platform.library.request.v1", "protocol": "1.0",
        "request_id": "req:local-signed-catalog",
        "correlation_id": "corr:local-signed-catalog",
        "operation": "library.catalog.snapshot.v1",
        "target_platform_id": platform_id,
        "expected_generation": generation,
        "expected_revision": revision,
        "idempotency_key": None,
        "created_at": (now - timedelta(seconds=1)).isoformat(),
        "deadline": (now + timedelta(seconds=10)).isoformat(),
        "parameters": {"limit": 32, "cursor": None, "kinds": []},
    }, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _query(endpoint, request):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(endpoint)
        client.sendall(request)
        response = bytearray()
        while not response.endswith(b"\n"):
            incoming = client.recv(65536)
            if not incoming:
                return bytes(response)
            response.extend(incoming)
            assert len(response) <= 65536
        return bytes(response).strip()


@pytest.mark.skipif(not LINUX, reason="actual disposable Linux SO_PEERCRED service")
def test_live_native_service_reads_only_owner_enrolled_signed_catalog(tmp_path):
    identity, current, state = provision(tmp_path)
    envelope, sign, keys = make_signed_catalog_fixture()
    now = datetime.now(timezone.utc)
    # Synthetic package only: re-sign a currently fresh catalog for the real
    # disposable installation identity created by the original repository.
    envelope["target_platform_id"] = current.identity.canonical_uuid
    envelope["catalog"]["target_platform_id"] = current.identity.canonical_uuid
    envelope["issued_at"] = (now - timedelta(seconds=3)).isoformat()
    envelope["expires_at"] = (now + timedelta(minutes=2)).isoformat()
    envelope["catalog"]["catalog_fresh_until"] = (now + timedelta(minutes=1)).isoformat()
    envelope["catalog"]["source"]["last_observed_at"] = now.isoformat()
    profile = tmp_path / "installed-library-profile.json"
    profile.write_text(json.dumps({
        "schema": "aegis.platform.library.installed-catalog-profile.v1",
        "signed_index_b64": b64encode(sign()).decode(),
        "publisher_public_key_b64": b64encode(
            keys["trusted_publisher_public_key"]
        ).decode(),
    }, sort_keys=True), encoding="utf-8")
    profile.chmod(0o600)
    publisher = dict(current=True)
    catalog = InstalledLibraryCatalogProvider(
        profile=profile,
        expected_publisher_key_sha256=keys["expected_publisher_key_sha256"],
        expected_source_platform_id="primary-library",
        expected_target_platform_id=current.identity.canonical_uuid,
        expected_catalog_generation=3, minimum_catalog_revision=7,
        publisher_key_current=lambda _: publisher["current"],
    )
    grants = PermissionStore(state)
    peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
    scope = {
        "platform_id": current.identity.canonical_uuid,
        "peer": peer,
        "operation": "library.catalog.snapshot.v1",
    }
    with PlatformServiceSession(
        identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256,
        installed_signed_catalog=catalog,
    ) as session:
        status = session.status()
        endpoint = status["management_endpoint"]
        raw = _request(status["platform_id"], status["generation"])
        # Kernel credential without owner grant is EOF, not even a denial.
        assert _query(endpoint, raw) == b""
        signed = grant_with_signed_owner(
            grants, "platform.library.read", scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        observed = json.loads(_query(endpoint, raw))
        assert observed["outcome"] == "OK"
        assert observed["data"]["source"]["source_id"] == "primary-library"
        assert observed["data"]["target_platform_id"] == current.identity.canonical_uuid
        assert "installed" not in json.dumps(observed)
        publisher["current"] = False
        assert _query(endpoint, _request(
            status["platform_id"], status["generation"],
        )) == b""
        publisher["current"] = True
        revoke_with_signed_owner(grants, signed.grant_id)
        assert _query(endpoint, _request(
            status["platform_id"], status["generation"],
        )) == b""
