"""Deferred mobile gateway concurrency admission and recovery contract."""
from http.client import HTTPConnection, HTTPException

from sofia.mobile.server import (
    MobileCompanionServer, MobileServerConfiguration, _MAX_INFLIGHT_REQUESTS,
)
from test.test_mobile_gateway import _gateway


def test_saturated_mobile_server_refuses_new_work_then_recovers(tmp_path):
    _, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("android-owner")
    server = MobileCompanionServer(
        gateway, credentials=gateway.credentials,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    slots = server._httpd._request_slots
    acquired = 0
    try:
        while slots.acquire(blocking=False):
            acquired += 1
        assert acquired == _MAX_INFLIGHT_REQUESTS
        host, port = server.address
        conn = HTTPConnection(host, port, timeout=2)
        try:
            try:
                conn.request("GET", "/v1/mobile/health",
                             headers={"Authorization": f"Bearer {token}"})
                assert conn.getresponse().status != 200
            except (OSError, HTTPException):
                pass
        finally:
            conn.close()

        for _ in range(acquired):
            slots.release()
        acquired = 0
        conn = HTTPConnection(host, port, timeout=2)
        try:
            conn.request("GET", "/v1/mobile/health",
                         headers={"Authorization": f"Bearer {token}"})
            assert conn.getresponse().status == 200
        finally:
            conn.close()
    finally:
        for _ in range(acquired):
            slots.release()
        server.close()
