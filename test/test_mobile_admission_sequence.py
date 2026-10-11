"""CA-6302 trusted canonical mobile admission ordering (tests deferred)."""
from contextlib import closing
import sqlite3

from test.test_mobile_gateway import _gateway


def test_logical_mobile_turn_admission_has_trusted_monotonic_order(tmp_path):
    app, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("android-owner")
    params = {
        "device_id": "android-owner", "private_mode": False,
    }
    first = gateway.chat(
        **params, message="Initial message",
        request_id="mobile-sequence-first-128",
    )
    second = gateway.chat(
        **params, message="Follow-up message",
        request_id="mobile-sequence-second-129",
    )
    a, b = first["delivery_receipt"], second["delivery_receipt"]
    assert (a["canonical_sequence"], b["canonical_sequence"]) == (1, 2)
    assert a["server_received_at"]
    assert a["logical_status"] == "completed"
    assert a["origin_device_id"] == "android-owner"
    replay = gateway.chat(
        **params, message="Initial message",
        request_id="mobile-sequence-first-128",
    )
    assert replay["delivery_receipt"] == a
    assert len(app.conversation.calls) == 2
    with closing(sqlite3.connect(gateway.state_path)) as db:
        rows = db.execute(
            "SELECT server_sequence,server_received_at "
            "FROM mobile_turn_receipt ORDER BY server_sequence",
        ).fetchall()
    assert [row[0] for row in rows] == [1, 2]
    assert all(row[1] for row in rows)


def test_unique_server_sequence_index_partitions_audience_and_generation(tmp_path):
    app, gateway = _gateway(tmp_path)
    gateway.credentials.enroll("android-owner")
    first = gateway.chat(
        device_id="android-owner", private_mode=False,
        message="Gen one, shared", request_id="first-gen-shared-100",
    )
    assert first["delivery_receipt"]["canonical_sequence"] == 1
    gateway.credentials.enroll("android-owner", rotate=True)
    # This storage-level case verifies the exclusive index can hold the
    # same ordinal for a different private audience and pairing generation.
    # Generation isolation of real social sessions has a separate test.
    with closing(sqlite3.connect(gateway.state_path)) as db, db:
        db.execute(
            "INSERT INTO mobile_turn_receipt("
            "request_id,device_id,presentation_mode,content_sha256,status,"
            "response_json,created_at,updated_at,credential_generation,"
            "server_sequence,server_received_at) "
            "VALUES(?,?,?,?,'uncertain',NULL,?,?,?,?,?)",
            ("different-generation-private", "android-owner",
             "private", "0" * 64,
             "2026-10-10T12:00:00+00:00",
             "2026-10-10T12:00:00+00:00",
             2, 1, "2026-10-10T12:00:00+00:00"),
        )
        rows = db.execute(
            "SELECT presentation_mode,credential_generation,server_sequence "
            "FROM mobile_turn_receipt ORDER BY presentation_mode",
        ).fetchall()
    assert rows == [("private", 2, 1), ("standard", 1, 1)]


def test_uncertain_turn_keeps_durable_server_order_and_is_not_replayed(tmp_path):
    from sofia.mobile.gateway import MobileDeliveryUncertain
    import pytest

    app, gateway = _gateway(tmp_path)
    gateway.credentials.enroll("android-owner")
    original = gateway._state_payload

    def fail_after_model(*args, **kwargs):
        raise RuntimeError("model persisted before receipt settlement")

    gateway._state_payload = fail_after_model
    request = {
        "device_id": "android-owner", "private_mode": False,
        "message": "Potentially accepted turn",
        "request_id": "uncertain-ordered-message-01",
    }
    with pytest.raises(RuntimeError):
        gateway.chat(**request)
    gateway._state_payload = original
    with pytest.raises(MobileDeliveryUncertain):
        gateway.chat(**request)
    succeeding = gateway.chat(
        device_id="android-owner", private_mode=False,
        message="New authorized turn", request_id="next-ordered-message-02",
    )
    assert succeeding["delivery_receipt"]["canonical_sequence"] == 2
    with closing(sqlite3.connect(gateway.state_path)) as db:
        row = db.execute(
            "SELECT status,server_sequence FROM mobile_turn_receipt "
            "WHERE request_id=?", (request["request_id"],),
        ).fetchone()
    assert row == ("uncertain", 1)
