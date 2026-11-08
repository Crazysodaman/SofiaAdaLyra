"""CORE-004: genuine loopback mTLS parsing negatives.

The tests use disposable certificates and an in-process gateway only.
They never open a personal Core, personal database, or Discord connection.
"""
from dataclasses import replace
from datetime import datetime, timezone
from http.client import HTTPSConnection
import json
from pathlib import Path
import ssl
import threading
from types import SimpleNamespace

import pytest

from sofia.platform.core_link import (
    CoreLinkEndpoint, CoreLinkServer, CoreLinkServerConfiguration,
    CoreLinkTLSCredentials, CoreLinkTransportError, PinnedCoreLinkClient,
)
from sofia.sdk.core_link import CoreLinkResponse, CoreLinkResponseStatus
from test.test_core_link_binding import activate, store
from test.test_core_link_conversation import request, tls_material


class _RecordingGateway:
    def __init__(self):
        self.calls = []

    def dispatch(self, *, certificate_public_key_sha256, request):
        self.calls.append((certificate_public_key_sha256, request))
        return CoreLinkResponse(
            request.request_id, CoreLinkResponseStatus.COMPLETED, {},
            datetime.now(timezone.utc),
        )

    def close(self):
        pass


@pytest.mark.parametrize("wire_case", ["duplicate_operation", "nested_duplicate", "nan"])
def test_core004_mtls_server_rejects_ambiguous_json_before_dispatch(tmp_path, wire_case):
    ca, (server_cert, server_key), (client_cert, client_key) = tls_material(tmp_path)
    gateway = _RecordingGateway()
    server = CoreLinkServer(
        CoreLinkServerConfiguration(
            listen_host="127.0.0.1", listen_port=0,
            server_certificate=server_cert,
            server_private_key=server_key,
            client_ca_file=ca, socket_timeout_seconds=5,
        ),
        gateway,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca))
    context.load_cert_chain(certfile=str(client_cert), keyfile=str(client_key))
    original = json.dumps(request("status", {}).to_payload(), sort_keys=True)
    if wire_case == "duplicate_operation":
        needle = '"operation": "status"'
        raw = original.replace(needle, needle + ', "operation": "status"', 1)
    elif wire_case == "nested_duplicate":
        raw = original.replace(
            '"payload": {}', '"payload": {"spoof": 1, "spoof": 2}', 1,
        )
    else:
        raw = original.replace('"payload": {}', '"payload": {"value": NaN}', 1)
    assert raw != original, "negative test did not mutate the actual wire frame"
    connection = HTTPSConnection(
        "localhost", server.address[1], context=context, timeout=5,
    )
    try:
        connection.request(
            "POST", "/v1/core-link", body=raw.encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 400
        assert gateway.calls == [], "ambiguous JSON reached the Core gateway"
    finally:
        connection.close()
        server.close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_core004_pinned_client_rejects_duplicate_json_response(monkeypatch, tmp_path):
    import sofia.platform.core_link.transport as transport

    registry = store(tmp_path)
    snapshot = registry.select(
        "binding:sofia-primary",
        expected_store_revision=activate(registry).revision,
    )
    binding = snapshot.selected()
    assert binding is not None
    endpoint = CoreLinkEndpoint(binding.endpoint_id, "localhost", 443)
    req = replace(
        request("status", {}),
        local_platform_id=binding.local_platform_id,
        remote_platform_id=binding.remote_platform_id,
        remote_core_identity_id=binding.remote_core_identity_id,
        remote_core_generation=binding.remote_core_generation,
        protocol=binding.protocol_version,
    )
    serialized = json.dumps(CoreLinkResponse(
        req.request_id, CoreLinkResponseStatus.COMPLETED, {},
        datetime.now(timezone.utc),
    ).to_payload())
    needle = '"status": "completed"'
    raw = serialized.replace(needle, needle + ', "status": "completed"', 1)
    assert raw != serialized
    posted = []

    class _Connection:
        def __init__(self, *_args, **_kwargs):
            self.sock = None

        def connect(self):
            self.sock = SimpleNamespace(
                getpeercert=lambda binary_form=False: b"synthetic-der",
            )

        def request(self, *_args, **_kwargs):
            posted.append(True)

        def getresponse(self):
            return SimpleNamespace(
                status=200, read=lambda size: raw.encode("utf-8"),
            )

        def close(self):
            pass

    monkeypatch.setattr(transport, "HTTPSConnection", _Connection)
    monkeypatch.setattr(
        transport, "public_key_fingerprint_from_der_certificate",
        lambda _cert: binding.trust_anchor_ref.removeprefix("sha256:"),
    )
    monkeypatch.setattr(
        PinnedCoreLinkClient, "_context",
        staticmethod(lambda _credentials: object()),
    )
    client = PinnedCoreLinkClient(
        registry, endpoint_resolver=lambda _id: endpoint,
        credential_resolver=lambda _ref: CoreLinkTLSCredentials(
            Path("/unused/ca.pem"), Path("/unused/client.pem"),
            Path("/unused/client.key"),
        ),
    )
    with pytest.raises(CoreLinkTransportError, match="invalid HTTP"):
        client.request(req)
    assert posted == [True]
