"""Canonical mobile turn receipts: replay, crash uncertainty, privacy and HTTP.

Authored during code-first work. Do not execute until the agreed later tests.
"""
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import sqlite3

import pytest

from sofia.mobile.gateway import (
    MobileCompanionGateway, MobileDeliveryConflict, MobileDeliveryUncertain,
)
from sofia.mobile.server import MobileCompanionServer, MobileServerConfiguration
from test.test_mobile_gateway import _gateway


def test_one_exact_mobile_request_returns_durable_receipt_not_duplicate_turn(tmp_path):
    app, gateway = _gateway(tmp_path)
    params = {
        "device_id": "phone-one",
        "message": "Remember this one exact event.",
        "private_mode": False,
        "request_id": "android-once-39e923fa",
    }
    a = gateway.chat(**params)
    b = gateway.chat(**params)
    assert a == b
    assert len(app.conversation.calls) == 1
    with closing(sqlite3.connect(gateway.state_path)) as db:
        row = db.execute(
            "SELECT status,content_sha256,response_json FROM mobile_turn_receipt "
            "WHERE request_id=?", (params["request_id"],),
        ).fetchone()
    assert row[0] == "completed"
    assert len(row[1]) == 64
    assert json.loads(row[2]) == a


def test_mobile_request_replay_with_changed_message_or_mode_is_rejected(tmp_path):
    app, gateway = _gateway(tmp_path)
    request = "android-conflict-340832a"
    gateway.chat(
        device_id="phone-one", message="Version one",
        private_mode=False, request_id=request,
    )
    with pytest.raises(MobileDeliveryConflict):
        gateway.chat(
            device_id="phone-one", message="Version two",
            private_mode=False, request_id=request,
        )
    with pytest.raises(MobileDeliveryConflict):
        gateway.chat(
            device_id="phone-one", message="Version one",
            private_mode=True, request_id=request,
        )
    assert len(app.conversation.calls) == 1


def test_processing_receipt_after_restart_must_never_replay(tmp_path):
    app, gateway = _gateway(tmp_path)
    req = "android-crash-5de2083d"
    # Simulated interruption after durable admission but before host reply.
    with closing(sqlite3.connect(gateway.state_path)) as db, db:
        from hashlib import sha256
        msg = "Might already have reached the model"
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO mobile_turn_receipt VALUES(?,?,?,?,?,?,?,?)",
            (req, "phone-one", "standard", sha256(msg.encode()).hexdigest(),
             "processing", None, now, now),
        )
    restarted = MobileCompanionGateway(app, state_path=gateway.state_path)
    with pytest.raises(MobileDeliveryUncertain):
        restarted.chat(
            device_id="phone-one", message=msg,
            private_mode=False, request_id=req,
        )
    assert app.conversation.calls == []


def test_exception_after_model_dispatch_is_not_retried_or_marked_completed(tmp_path):
    app, gateway = _gateway(tmp_path)
    original = gateway._state_payload
    def broken_after_response(*args, **kwargs):
        raise RuntimeError("transport construction failed after reply persisted")
    gateway._state_payload = broken_after_response
    params = {
        "device_id": "phone-one", "message": "One time only",
        "private_mode": False, "request_id": "android-uncertain-671f32a",
    }
    with pytest.raises(RuntimeError):
        gateway.chat(**params)
    assert len(app.conversation.calls) == 1
    gateway._state_payload = original
    with pytest.raises(MobileDeliveryUncertain):
        gateway.chat(**params)
    assert len(app.conversation.calls) == 1


def test_http_duplicate_mobile_send_returns_same_response_and_conflict_409(tmp_path):
    app, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("phone-one")
    server = MobileCompanionServer(
        gateway, credentials=gateway.credentials,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    host, port = server.address

    def send(payload):
        connection = HTTPConnection(host, port, timeout=5)
        try:
            connection.request(
                "POST", "/v1/mobile/chat", body=json.dumps(payload),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    body = {
        "device_id": "phone-one", "message": "Exactly one HTTP turn",
        "private_mode": False, "request_id": "android-http-927352a",
    }
    try:
        first_status, first = send(body)
        second_status, second = send(body)
        assert (first_status, second_status) == (200, 200)
        assert first == second
        assert len(app.conversation.calls) == 1
        status, rejected = send({**body, "message": "Changed"})
        assert status == 409
        assert rejected["error"] == "delivery_conflict_or_uncertain"
        assert len(app.conversation.calls) == 1
    finally:
        server.close()
