"""Fleet peers cannot force unbounded response allocation after TLS admission."""
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest

from sofia.platform.distributed import https_transport as transport_module
from sofia.platform.distributed.https_transport import (
    HttpsTransportError, MAX_RESPONSE_BYTES, PinnedHttpsRemoteTransport,
)
from sofia.platform.distributed.model import (
    DistributedNode, NodeEndpoint, NodeEnrollment, NodeTransport,
)


def _request(monkeypatch, body, status=200, *, pin_matches=True):
    reads = []
    closed = []
    stream = BytesIO(body)

    def read(amount):
        reads.append(amount)
        return stream.read(amount)

    connection = SimpleNamespace(
        connect=lambda: None,
        sock=SimpleNamespace(getpeercert=lambda **kwargs: b"test certificate"),
        request=lambda *args, **kwargs: None,
        getresponse=lambda: SimpleNamespace(status=status, read=read),
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(transport_module, "HTTPSConnection", lambda *a, **k: connection)
    monkeypatch.setattr(PinnedHttpsRemoteTransport, "_context", lambda self: None)
    monkeypatch.setattr(
        transport_module, "public_key_fingerprint_from_der_certificate",
        lambda certificate: ("a" if pin_matches else "b") * 64,
    )
    enrollment = NodeEnrollment(
        DistributedNode(uuid4(), "test peer"), "a" * 64,
        datetime.now(timezone.utc), "test owner",
    )
    transport = PinnedHttpsRemoteTransport(
        lambda _: NodeEndpoint("localhost", 443, NodeTransport.HTTPS),
        ca_file="unused", client_certificate="unused", client_private_key="unused",
    )
    return lambda: transport._request(enrollment, "GET", "/v1/identity"), reads, closed


@pytest.mark.parametrize("status", [200, 500])
def test_oversized_response_is_rejected_before_json_or_error_processing(monkeypatch, status):
    request, reads, closed = _request(monkeypatch, b"x" * (MAX_RESPONSE_BYTES + 100), status)
    with pytest.raises(HttpsTransportError, match="exceeds maximum size"):
        request()
    assert reads == [MAX_RESPONSE_BYTES + 1]
    assert closed == [True]


def test_exact_limit_valid_json_is_accepted(monkeypatch):
    request, reads, closed = _request(monkeypatch, b'"' + b"a" * (MAX_RESPONSE_BYTES - 2) + b'"')
    assert len(request()) == MAX_RESPONSE_BYTES - 2
    assert reads == [MAX_RESPONSE_BYTES + 1]
    assert closed == [True]


@pytest.mark.parametrize("body, status, message", [
    (b"invalid", 200, "invalid JSON"),
    (b"denied", 403, "agent HTTP 403"),
])
def test_bounded_failures_close_connection(monkeypatch, body, status, message):
    request, reads, closed = _request(monkeypatch, body, status)
    with pytest.raises(HttpsTransportError, match=message):
        request()
    assert reads == [MAX_RESPONSE_BYTES + 1]
    assert closed == [True]


def test_pin_failure_never_reads_response(monkeypatch):
    request, reads, closed = _request(monkeypatch, b"{}", pin_matches=False)
    with pytest.raises(HttpsTransportError, match="pin"):
        request()
    assert reads == []
    assert closed == [True]
