"""The real PlatformServiceSession, canonical SAFE and native AF_UNIX broker.

Owner approvals use the existing repository fixture's genuinely verified
one-use P-256 WebAuthn assertion, not an owner-name or mocked grant. The
fixture provisions disposable trust, not an owner-enrolled production key.
This same-UID developer test is NOT the external B1 installed-host receipt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import socket
import sys

import pytest

from sofia.platform.run.platform_service import PlatformServiceSession
from sofia.platform.safe.permissions import PermissionStore
from sofia.sdk.platform_management_client import read_linux_platform_status
from test.owner_auth_fixture import (
    grant_with_signed_owner, revoke_with_signed_owner,
    resume_with_signed_owner_proof,
)
from test.test_platform_service_session import provision

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"),
    reason="real Linux SO_PEERCRED service and canonical SAFE required",
)


def _read(session: PlatformServiceSession, generation: int):
    status = session.status()
    return read_linux_platform_status(
        socket_path=Path(status["management_endpoint"]),
        expected_platform_id=status["platform_id"],
        expected_generation=generation,
        installed_service_uid=os.geteuid(),
        installed_service_gid=os.getegid(),
        installed_service_pid=os.getpid(),
    )


def test_real_platform_service_owner_approved_grant_stop_revoke_and_restart(
    tmp_path, monkeypatch,
):
    """End-to-end on one real service and one canonical SQLite SAFE writer."""
    # Never borrow an arbitrary exported systemd directory or real installed
    # service. The owned private developer socket remains 0700/0600 only.
    monkeypatch.delenv("RUNTIME_DIRECTORY", raising=False)
    identity, installation, state = provision(tmp_path)
    permissions = PermissionStore(state)
    platform_id = installation.identity.canonical_uuid
    principal = f"unix:uid:{os.geteuid()}:gid:{os.getegid()}"
    scope = {
        "platform_id": platform_id,
        "peer": principal,
        "operation": "platform.status",
    }
    signed_grant_id = None

    with PlatformServiceSession(
        identity.home, state, platform_id, installation.public_key_sha256,
    ) as service:
        first = service.status()
        first_generation = first["generation"]
        first_endpoint = first["management_endpoint"]
        assert first["management_listening"] is True
        assert first["core_started"] is False
        # The same kernel UID has socket access but NO SAFE enrollment.
        with pytest.raises(PermissionError, match="refused|unavailable"):
            _read(service, first_generation)

        grant = grant_with_signed_owner(
            permissions, "platform.management.read", scope=scope,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        signed_grant_id = grant.grant_id
        accepted = _read(service, first_generation)
        assert accepted.outcome == "OK"
        assert accepted.request_id.startswith("req:")
        assert accepted.generation == first_generation
        assert accepted.platform_id == platform_id
        assert accepted.data == {
            "platform_id": platform_id,
            "generation": first_generation,
            "core_started": False,
            "operator_stop": False,
        }

        service.stop.set(
            active=True, updated_by="Sparks",
            reason="A IG-001 disposable STOP negative",
        )
        stopped = _read(service, first_generation)
        assert stopped.outcome == "DENIED"
        assert stopped.denial_code == "STOPPED"
        assert stopped.data is None

        # Resume requires a FRESH signed, one-use owner approval bound to the
        # STOP revision, not the pre-STOP status grant or a claimed owner name.
        resume_with_signed_owner_proof(
            service.stop, reason="A IG-001 disposable approved resume",
        )
        assert _read(service, first_generation).outcome == "OK"

    assert not os.path.lexists(first_endpoint)
    with PlatformServiceSession(
        identity.home, state, platform_id, installation.public_key_sha256,
    ) as service:
        second = service.status()
        assert second["generation"] > first_generation
        assert second["management_endpoint"] != first_endpoint
        with pytest.raises((FileNotFoundError, PermissionError, OSError)):
            read_linux_platform_status(
                socket_path=Path(first_endpoint),
                expected_platform_id=platform_id,
                expected_generation=first_generation,
                installed_service_uid=os.geteuid(),
                installed_service_gid=os.getegid(),
                installed_service_pid=os.getpid(),
            )
        stale = _read(service, first_generation)
        assert stale.outcome == "DENIED"
        assert stale.denial_code == "STALE_GENERATION"
        assert stale.data is None
        assert _read(service, second["generation"]).outcome == "OK"

        assert signed_grant_id is not None
        revoke_with_signed_owner(permissions, signed_grant_id)
        with pytest.raises(PermissionError, match="refused|unavailable"):
            _read(service, second["generation"])
        assert service.status()["core_started"] is False
        assert not list(tmp_path.rglob("sofia.db"))
