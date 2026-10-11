"""Operator-issued mobile bearer identity and revocation boundaries.

Authored only. Do NOT execute until the owner's deferred test campaign.
"""
from contextlib import closing
from http.client import HTTPConnection
import json
import sqlite3

import pytest

from sofia.mobile.gateway import MobileCompanionGateway
from sofia.mobile.pairing import MobileDeviceCredentialStore
from sofia.mobile.provisioning import MobileProvisioning, mobile_companion_ready
from sofia.mobile.server import MobileCompanionServer, MobileServerConfiguration
from test.test_mobile_gateway import _gateway


def _request(server, token, *, method="POST", path="/v1/mobile/state", payload=None):
    host, port = server.address
    connection = HTTPConnection(host, port, timeout=5)
    try:
        connection.request(
            method, path,
            body=None if payload is None else json.dumps(payload),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def test_each_phone_gets_distinct_unrecoverable_secrets_in_one_canonical_database(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    store = MobileDeviceCredentialStore(state)
    a = store.enroll("android-alpha")
    b = store.enroll("android-beta")
    assert a != b
    assert a.startswith("sm1_") and b.startswith("sm1_")
    assert store.authenticate(a) == "android-alpha"
    assert store.authenticate(b) == "android-beta"
    assert store.active_count() == 2
    assert store.authenticate("t" * 40) is None
    with closing(sqlite3.connect(state)) as db:
        raw = repr(db.execute("SELECT * FROM mobile_device_credential").fetchall())
    assert a not in raw and b not in raw
    assert len(store.list_devices()) == 2


def test_revoke_and_rotate_refuse_old_token_without_affecting_other_phone(tmp_path):
    state = tmp_path / "sofia.db"
    state.touch()
    store = MobileDeviceCredentialStore(state)
    a = store.enroll("android-alpha")
    b = store.enroll("android-beta")
    with pytest.raises(PermissionError, match="explicit --rotate"):
        store.enroll("android-alpha")
    newer = store.enroll("android-alpha", rotate=True)
    assert newer != a
    assert store.authenticate(a) is None
    assert store.authenticate(newer) == "android-alpha"
    assert store.authenticate(b) == "android-beta"
    assert store.revoke("android-alpha")
    assert not store.revoke("android-alpha")
    assert store.authenticate(newer) is None
    assert store.authenticate(b) == "android-beta"
    assert store.list_devices()[0].status == "revoked"
    with closing(sqlite3.connect(state)) as db:
        events = [r[0] for r in db.execute(
            "SELECT action FROM mobile_device_credential_audit "
            "WHERE device_id='android-alpha' ORDER BY id"
        )]
    assert events == ["enrolled", "rotated", "revoked"]


def test_http_bearer_is_bound_to_actual_registered_device_on_all_paths(tmp_path):
    _, gateway = _gateway(tmp_path)
    token_a = gateway.credentials.enroll("android-alpha")
    token_b = gateway.credentials.enroll("android-beta")
    server = MobileCompanionServer(
        gateway, credentials=gateway.credentials,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    try:
        assert _request(server, token_a, method="GET",
                        path="/v1/mobile/health")[0] == 200
        accepted, _ = _request(
            server, token_a,
            payload={"device_id": "android-alpha", "private_mode": False},
        )
        assert accepted == 200
        for path, payload in (
            ("/v1/mobile/state", {
                "device_id": "android-beta", "private_mode": False,
            }),
            ("/v1/mobile/chat", {
                "device_id": "android-beta", "private_mode": False,
                "message": "must never reach other phone",
                "request_id": "android-wrong-target-123",
            }),
            ("/v1/mobile/main/page", {
                "device_id": "android-beta", "private_mode": False,
                "before": None, "limit": 5,
            }),
            ("/v1/mobile/notifications/claim", {
                "device_id": "android-beta", "private_mode": False,
            }),
            ("/v1/mobile/notifications/ack", {
                "device_id": "android-beta", "notification_id": "act:other",
            }),
            ("/v1/mobile/sensors", {
                "device_id": "android-beta", "observed_at": "2026-10-10T12:00:00Z",
            }),
        ):
            denied, _ = _request(server, token_a, path=path, payload=payload)
            assert denied == 403, path
        own, _ = _request(
            server, token_b,
            payload={"device_id": "android-beta", "private_mode": False},
        )
        assert own == 200
    finally:
        server.close()


def test_revocation_is_effective_immediately_without_server_restart(tmp_path):
    _, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("android-alpha")
    server = MobileCompanionServer(
        gateway, credentials=gateway.credentials,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    try:
        assert _request(server, token, method="GET",
                        path="/v1/mobile/health")[0] == 200
        gateway.credentials.revoke("android-alpha")
        assert _request(server, token, method="GET",
                        path="/v1/mobile/health")[0] == 401
    finally:
        server.close()


def test_mobile_delivery_ready_requires_active_enrollment(tmp_path, monkeypatch):
    state = tmp_path / "sofia.db"
    state.touch()
    monkeypatch.setenv("SOFIA_MOBILE_ENABLED", "1")
    monkeypatch.delenv("SOFIA_MOBILE_TOKEN", raising=False)
    assert not mobile_companion_ready(state)
    store = MobileDeviceCredentialStore(state)
    store.enroll("android-alpha")
    assert mobile_companion_ready(state)
    store.revoke("android-alpha")
    assert not mobile_companion_ready(state)


def test_retired_global_mobile_token_is_not_a_server_fallback(tmp_path):
    _, gateway = _gateway(tmp_path)
    with pytest.raises(TypeError, match="credentials"):
        MobileCompanionServer(
            gateway, token="legacy-shared-token-that-would-have-worked",
            configuration=MobileServerConfiguration(port=0),
        )
