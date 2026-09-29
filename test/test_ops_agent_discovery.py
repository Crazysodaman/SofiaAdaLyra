from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import sofia.ops.agent_discovery as discovery_module
from sofia.ops import AgentDiscoveryTarget, MtlsAgentDiscoverySource


NODE_ID = UUID("11111111-2222-3333-4444-555555555555")


class FakeSocket:
    def getpeercert(self, *, binary_form=False):
        assert binary_form is True
        return b"fake-cert"


class FakeResponse:
    status = 200
    def read(self):
        return (
            b'{"node_id":"11111111-2222-3333-4444-555555555555",'
            b'"name":"Artemis","protocol_version":"1.0"}'
        )


class FakeConnection:
    def __init__(self, hostname, port, *, context, timeout):
        self.hostname = hostname
        self.port = port
        self.context = context
        self.timeout = timeout
        self.sock = FakeSocket()
        self.closed = False

    def connect(self):
        return None

    def request(self, method, path, headers=None):
        assert method == "GET"
        assert path == "/v1/identity"

    def getresponse(self):
        return FakeResponse()

    def close(self):
        self.closed = True


def _source(monkeypatch, **target_overrides):
    monkeypatch.setattr(
        discovery_module,
        "HTTPSConnection",
        FakeConnection,
    )
    monkeypatch.setattr(
        discovery_module,
        "public_key_fingerprint_from_der_certificate",
        lambda cert: "a" * 64,
    )
    source = MtlsAgentDiscoverySource(
        (
            AgentDiscoveryTarget(
                hostname="artemis.local",
                platform="windows",
                architecture="amd64",
                inside_approved_scope=True,
                **target_overrides,
            ),
        ),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
    )
    monkeypatch.setattr(
        source,
        "_context",
        lambda: SimpleNamespace(),
    )
    return source


def test_mtls_agent_discovery_returns_untrusted_identity_evidence(monkeypatch):
    observation = _source(monkeypatch).discover()[0]

    assert observation.host_id == "Artemis"
    assert observation.hostname == "artemis.local"
    assert observation.observed_node_id == NODE_ID
    assert observation.observed_public_key_sha256 == "a" * 64
    assert observation.installed_protocol_version == "1.0"
    assert observation.observed_endpoint_hostname == "artemis.local"
    assert observation.observed_endpoint_port == 7443


def test_out_of_scope_target_is_never_contacted(monkeypatch):
    contacted = []

    class ForbiddenConnection:
        def __init__(self, *args, **kwargs):
            contacted.append(True)

    monkeypatch.setattr(
        discovery_module,
        "HTTPSConnection",
        ForbiddenConnection,
    )
    source = MtlsAgentDiscoverySource(
        (
            AgentDiscoveryTarget(
                hostname="unknown.local",
                inside_approved_scope=False,
            ),
        ),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
    )

    observation = source.discover()[0]

    assert contacted == []
    assert observation.inside_approved_scope is False
    assert observation.observed_node_id is None
    assert observation.observed_public_key_sha256 is None


def test_incompatible_protocol_is_not_admitted_as_discovery_evidence(
    monkeypatch,
):
    class IncompatibleResponse(FakeResponse):
        def read(self):
            return (
                b'{"node_id":"11111111-2222-3333-4444-555555555555",'
                b'"name":"Artemis","protocol_version":"2.0"}'
            )

    class IncompatibleConnection(FakeConnection):
        def getresponse(self):
            return IncompatibleResponse()

    monkeypatch.setattr(
        discovery_module,
        "HTTPSConnection",
        IncompatibleConnection,
    )
    monkeypatch.setattr(
        discovery_module,
        "public_key_fingerprint_from_der_certificate",
        lambda cert: "a" * 64,
    )
    source = MtlsAgentDiscoverySource(
        (
            AgentDiscoveryTarget(
                hostname="artemis.local",
                inside_approved_scope=True,
            ),
        ),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
    )
    monkeypatch.setattr(source, "_context", lambda: SimpleNamespace())

    assert source.discover() == ()
