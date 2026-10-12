"""Deferred regression: recovery queries credentials and receipt in one SQLite snapshot."""
from hashlib import sha256

from test.test_mobile_gateway import _gateway


def test_status_pins_read_snapshot_before_any_pairing_or_receipt_lookup(
    tmp_path, monkeypatch,
):
    app, gateway = _gateway(tmp_path)
    bearer = gateway.credentials.enroll("android-owner")
    original_connect = gateway._connect
    statements = []

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(gateway, "_connect", traced_connect)
    status = gateway.dispatch_authenticated(
        credential=bearer,
        operation="/v1/mobile/delivery/status",
        payload={
            "device_id": "android-owner",
            "private_mode": False,
            "request_id": "no-previous-delivery",
            "content_sha256": sha256(b"original bytes").hexdigest(),
        },
    )
    assert status == {"status": "not_found"}
    queries = [entry.strip().upper() for entry in statements]
    begin = next(i for i, sql in enumerate(queries) if sql == "BEGIN")
    credential = next(
        i for i, sql in enumerate(queries)
        if i > begin and "SELECT GENERATION FROM MOBILE_DEVICE_CREDENTIAL" in sql
    )
    receipt = next(
        i for i, sql in enumerate(queries)
        if "FROM MOBILE_TURN_RECEIPT WHERE REQUEST_ID=" in sql
    )
    assert begin < credential < receipt
    assert app.conversation.calls == []
