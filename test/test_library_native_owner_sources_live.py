"""D028 local Linux native owner-only source status through real Platform IPC.

Uses original Platform RUN lease, kernel SO_PEERCRED and original owner-SAFE
one-use approval helper with a disposable signed owner identity. This is not
a production signed release or a commercial/multi-tenant test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys

import pytest

from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from test.owner_auth_fixture import grant_with_signed_owner, revoke_with_signed_owner
from test.test_platform_service_session import provision

LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


def _request(platform_id: str, generation: int, *, operation: str) -> bytes:
    now = datetime.now(timezone.utc)
    payload = {
        "schema": "aegis.platform.library.request.v1",
        "protocol": "1.0",
        "request_id": "request:owner-source-live",
        "correlation_id": "correlation:owner-source-live",
        "operation": operation,
        "target_platform_id": platform_id,
        "expected_generation": generation,
        "expected_revision": 0,
        "idempotency_key": None,
        "created_at": (now - timedelta(seconds=1)).isoformat(),
        "deadline": (now + timedelta(seconds=10)).isoformat(),
        "parameters": {},
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8") + b"\n"


def _query(path: str, request: bytes) -> bytes:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(path)
        connection.sendall(request)
        chunks = bytearray()
        while not chunks.endswith(b"\n"):
            observed = connection.recv(32768)
            if not observed:
                return bytes(chunks)
            chunks.extend(observed)
            if len(chunks) > 32768:
                raise RuntimeError("oversized owner-only status")
        return bytes(chunks).strip()


@pytest.mark.skipif(not LINUX, reason="real native Linux SO_PEERCRED service")
def test_single_owner_unenrolled_native_sources_cannot_be_read_without_safe_grant(
    tmp_path,
):
    identity, current, state = provision(tmp_path)
    platform_id = current.identity.canonical_uuid
    permissions = PermissionStore(state)
    peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
    with PlatformServiceSession(
        identity.home, state, platform_id, current.public_key_sha256,
    ) as service:
        status = service.status()
        assert status["management_listening"] is True
        endpoint = status["management_endpoint"]
        raw = _request(
            platform_id, status["generation"],
            operation="library.sources.snapshot.v1",
        )
        assert _query(endpoint, raw) == b""  # exact unknown peer => EOF
        scope = {
            "platform_id": platform_id,
            "peer": peer,
            "operation": "library.sources.snapshot.v1",
        }
        grant = grant_with_signed_owner(
            permissions, "platform.library.read",
            scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        observed = json.loads(_query(endpoint, raw))
        assert observed["outcome"] == "OK"
        assert observed["platform_id"] == platform_id
        assert observed["platform_generation"] == status["generation"]
        assert observed["data"] == {
            "schema": "aegis.library.owner-sources.v1",
            "owner_mode": "SINGLE_OWNER_PRIVATE",
            "source_platform_id": None,
            "publisher_state": "UNENROLLED",
            "catalog_state": "UNAVAILABLE",
            "hub_state": "CLOSED",
            "served_chunks": 0,
            "served_bytes": 0,
        }
        # A source-status scope grants neither catalog reads nor installation.
        catalog = _request(
            platform_id, status["generation"],
            operation="library.catalog.snapshot.v1",
        )
        assert _query(endpoint, catalog) == b""
        revoke_with_signed_owner(permissions, grant.grant_id)
        assert _query(endpoint, raw) == b""
