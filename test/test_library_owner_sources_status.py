"""D028 owner-only source status, Python/Rust shared strict wire contract.

Synthetic disposable native identities are not actual kernel credentials,
production owner approvals or signed release evidence. The live Platform
listener supplies those independently and checks SAFE for every read.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sofia.platform.run.library_owner_sources import owner_library_source_status
from sofia.platform.run.library_owner_trust import OwnerLibraryTrustStore
from sofia.platform.run.library_read_authority import SOURCES_OPERATION
from sofia.platform.run.library_read_dispatch import LibraryReadDispatcher
from sofia.sdk.platform_library import (
    UntrustedLibraryRequest, UntrustedLibraryResponse,
)
from test.test_platform_service_session import provision

FIXTURES = Path(__file__).resolve().parents[1] / "contracts" / "platform"
NOW = datetime.fromisoformat("2026-11-08T04:00:02+00:00")
PEER = "unix:uid:1000:gid:1000"


def _fixtures():
    request = (FIXTURES / "library-request-personal-sources-v1.json").read_bytes()
    response = (FIXTURES / "library-response-personal-sources-v1.json").read_bytes()
    return request, response


def test_shared_owner_status_fixtures_are_strictly_correlated():
    raw, body = _fixtures()
    req = UntrustedLibraryRequest.parse(raw, now=NOW)
    assert req.operation == SOURCES_OPERATION
    assert req.expected_revision == 0
    accepted = UntrustedLibraryResponse.parse(body, expected=req, now=NOW)
    assert accepted.outcome == "OK"
    assert accepted.data["source_platform_id"] == "platform:hub"
    assert accepted.data["served_bytes"] == 3145728
    assert "installed" not in json.dumps(accepted.data)


@pytest.mark.parametrize("mutation", [
    {"publisher_state": "UNENROLLED"},
    {"publisher_state": "REVOKED"},
    {"source_platform_id": None},
    {"hub_state": "READY"},
    {"catalog_state": "UNSIGNED"},
    {"served_chunks": -1},
    {"served_bytes": True},
    {"owner_mode": "MULTI_TENANT"},
    {"owner_proof": "secret"},
])
def test_sources_status_rejects_untrusted_authority_and_inconsistent_states(
    mutation,
):
    raw, body = _fixtures()
    req = UntrustedLibraryRequest.parse(raw, now=NOW)
    reply = json.loads(body)
    reply["data"].update(mutation)
    with pytest.raises((ValueError, PermissionError)):
        UntrustedLibraryResponse.parse(
            json.dumps(reply).encode(), expected=req, now=NOW,
        )


def test_owner_unenrolled_host_reports_accurate_unknown_states(tmp_path):
    identity, current, state = provision(tmp_path)
    store = OwnerLibraryTrustStore(
        state, platform_id=current.identity.canonical_uuid,
    )
    current_status = {
        "platform_id": current.identity.canonical_uuid,
        "generation": 7, "operator_stop": False,
    }
    data = owner_library_source_status(
        status=current_status, owner_trust=store, hosted_hub=None,
    )
    assert data["owner_mode"] == "SINGLE_OWNER_PRIVATE"
    assert data["source_platform_id"] is None
    assert data["publisher_state"] == "UNENROLLED"
    assert data["catalog_state"] == "UNAVAILABLE"
    assert data["hub_state"] == "CLOSED"
    assert data["served_chunks"] == 0
    assert data["served_bytes"] == 0


def test_owner_sources_status_denies_stop_and_foreign_source(tmp_path):
    identity, current, state = provision(tmp_path)
    store = OwnerLibraryTrustStore(
        state, platform_id=current.identity.canonical_uuid,
    )
    with pytest.raises(PermissionError, match="STOP-free"):
        owner_library_source_status(
            status={
                "platform_id": current.identity.canonical_uuid,
                "generation": 7, "operator_stop": True,
            },
            owner_trust=store, hosted_hub=None,
        )
    with pytest.raises(PermissionError, match="another Platform"):
        owner_library_source_status(
            status={
                "platform_id": "different-platform",
                "generation": 7, "operator_stop": False,
            },
            owner_trust=store, hosted_hub=None,
        )


def test_native_source_status_is_current_only_with_real_hub_grant():
    observed = {
        "platform_id": "platform:recipient",
        "generation": 7, "operator_stop": False,
    }
    expected = {
        "schema": "aegis.library.owner-sources.v1",
        "owner_mode": "SINGLE_OWNER_PRIVATE",
        "source_platform_id": "platform:hub",
        "publisher_state": "CURRENT",
        "catalog_state": "CURRENT",
        "hub_state": "OPEN_IDLE",
        "served_chunks": 0,
        "served_bytes": 0,
    }
    owner_allowed = {"current": True}
    dispatcher = LibraryReadDispatcher(
        current_status=lambda: dict(observed),
        authorize_os_peer=lambda peer, op: (
            owner_allowed["current"] and peer == PEER
            and op == SOURCES_OPERATION
        ),
        installed_signed_catalog=lambda: None,
        read_owner_sources=lambda: dict(expected),
        clock=lambda: NOW,
    )
    raw, _body = _fixtures()
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "OK"
    assert reply["data"]["hub_state"] == "OPEN_IDLE"
    req = UntrustedLibraryRequest.parse(raw, now=NOW)
    accepted = UntrustedLibraryResponse.parse(
        json.dumps(reply).encode(), expected=req, now=NOW,
    )
    assert accepted.outcome == "OK"
    owner_allowed["current"] = False
    with pytest.raises(PermissionError, match="owner-enrolled"):
        dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)


def test_unenrolled_peer_gets_no_owner_status_even_when_hub_active():
    raw, _body = _fixtures()
    dispatcher = LibraryReadDispatcher(
        current_status=lambda: {
            "platform_id": "platform:recipient",
            "generation": 7, "operator_stop": False,
        },
        authorize_os_peer=lambda *_: False,
        installed_signed_catalog=lambda: None,
        read_owner_sources=lambda: (_ for _ in ()).throw(
            AssertionError("must never read Hub state for an unknown caller")
        ),
        clock=lambda: NOW,
    )
    with pytest.raises(PermissionError, match="owner-enrolled"):
        dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
