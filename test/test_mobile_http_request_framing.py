"""Deferred authenticated mobile HTTP framing and delivery protections."""
from http.client import HTTPConnection
import json
import socket

from sofia.mobile.server import MobileCompanionServer, MobileServerConfiguration
from test.test_mobile_gateway import _gateway


def _setup(tmp_path):
    _, gateway = _gateway(tmp_path)
    token = gateway.credentials.enroll("android-owner")
    server = MobileCompanionServer(
        gateway, credentials=gateway.credentials,
        configuration=MobileServerConfiguration(port=0),
    )
    server.start()
    return gateway, token, server


def _payload():
    return json.dumps({
        "device_id": "android-owner", "private_mode": False,
    }).encode("utf-8")


def test_duplicated_request_content_length_cannot_reach_canonical_gateway(tmp_path):
    gateway, token, server = _setup(tmp_path)
    host, port = server.address
    raw = _payload()
    conn = HTTPConnection(host, port, timeout=2)
    try:
        conn.putrequest("POST", "/v1/mobile/state")
        conn.putheader("Authorization", f"Bearer {token}")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(len(raw)))
        conn.putheader("Content-Length", str(len(raw) + 5))
        conn.endheaders(raw)
        response = conn.getresponse()
        assert response.status == 400
        assert json.loads(response.read())["error"] == "invalid_request"
    finally:
        conn.close()
        server.close()


def test_truncated_request_body_cannot_dispatch_and_server_recovers(tmp_path):
    gateway, token, server = _setup(tmp_path)
    host, port = server.address
    raw = _payload()
    try:
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.settimeout(3)
            request = (
                f"POST /v1/mobile/state HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Authorization: Bearer {token}\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(raw) + 50}\r\n"
                "Connection: close\r\n\r\n"
            ).encode("ascii") + raw
            sock.sendall(request)
            sock.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            assert b"400" in b"".join(chunks).split(b"\r\n", 1)[0]

        conn = HTTPConnection(host, port, timeout=2)
        try:
            conn.request(
                "POST", "/v1/mobile/state", body=raw,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            assert conn.getresponse().status == 200
        finally:
            conn.close()
    finally:
        server.close()
