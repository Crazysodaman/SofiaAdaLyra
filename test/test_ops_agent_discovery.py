from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

import sofia.ops.agent_discovery as discovery_module
from sofia.ops.agent_discovery import create_configured_fleet_discovery_source
from sofia.ops import (
    AgentDiscoveryTarget,
    FleetDiscoveryEvidence,
    CombinedFleetDiscoverySource,
    MtlsAgentDiscoverySource,
    ScopedHostPresenceDiscoverySource,
    ScopedMtlsAgentDiscoverySource,
)


NODE_ID = UUID("11111111-2222-3333-4444-555555555555")


class FakeSocket:
    def getpeercert(self, *, binary_form=False):
        assert binary_form is True
        return b"fake-cert"


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload


class FakeConnection:
    def __init__(self, hostname, port, *, context, timeout):
        self.hostname = hostname
        self.port = port
        self.context = context
        self.timeout = timeout
        self.sock = FakeSocket()
        self.closed = False
        self.path = None

    def connect(self):
        return None

    def request(self, method, path, headers=None):
        assert method == "GET"
        assert path in ("/v1/identity", "/v1/capabilities")
        self.path = path

    def getresponse(self):
        if self.path == "/v1/identity":
            return FakeResponse(
                (
                    b'{"node_id":"11111111-2222-3333-4444-555555555555",'
                    b'"name":"Artemis","protocol_version":"1.0"}'
                )
            )
        return FakeResponse(
            (
                b'{"node_id":"11111111-2222-3333-4444-555555555555",'
                b'"protocol_version":"1.0","capabilities":['
                b'{"name":"system.inspect","operations":["latest"]},'
                b'{"name":"ops.telemetry","operations":["latest"]}]}'
            )
        )

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
    assert observation.capabilities_verified is True
    assert observation.capability_names == (
        "ops.telemetry",
        "system.inspect",
    )


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
    class IncompatibleConnection(FakeConnection):
        def getresponse(self):
            if self.path == "/v1/identity":
                return FakeResponse(
                    (
                        b'{"node_id":"11111111-2222-3333-4444-555555555555",'
                        b'"name":"Artemis","protocol_version":"2.0"}'
                    )
                )
            return super().getresponse()

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


def test_scoped_discovery_refuses_oversized_network():
    source = ScopedMtlsAgentDiscoverySource(
        explicit_targets=(),
        scopes=("10.0.0.0/24",),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
        max_hosts_per_scope=32,
    )

    with pytest.raises(ValueError, match="exceeds max_hosts_per_scope"):
        source._scope_addresses()


def test_scoped_discovery_expands_only_configured_hosts(monkeypatch):
    source = ScopedMtlsAgentDiscoverySource(
        explicit_targets=(),
        scopes=("192.0.2.0/30",),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
        max_hosts_per_scope=8,
    )

    assert source._scope_addresses() == (
        "192.0.2.1",
        "192.0.2.2",
    )


def test_scoped_discovery_passes_only_reachable_targets_to_mtls(
    monkeypatch,
):
    observed = []

    source = ScopedMtlsAgentDiscoverySource(
        explicit_targets=(
            AgentDiscoveryTarget(
                hostname="artemis.local",
                inside_approved_scope=True,
            ),
        ),
        scopes=("192.0.2.0/30",),
        ca_file="ca.pem",
        client_certificate="client.pem",
        client_private_key="client.key",
        max_hosts_per_scope=8,
    )

    monkeypatch.setattr(
        source,
        "_reachable",
        lambda address: (
            AgentDiscoveryTarget(
                hostname=address,
                inside_approved_scope=True,
            )
            if address.endswith(".2")
            else None
        ),
    )

    def fake_discover(self):
        observed.extend(
            (target.hostname, target.port)
            for target in self.targets
        )
        return ()

    monkeypatch.setattr(
        discovery_module.MtlsAgentDiscoverySource,
        "discover",
        fake_discover,
    )

    assert source.discover() == ()
    assert ("artemis.local", 7443) in observed
    assert ("192.0.2.2", 7443) in observed
    assert ("192.0.2.1", 7443) not in observed


def test_bare_host_presence_creates_untrusted_unknown_evidence(monkeypatch):
    source = ScopedHostPresenceDiscoverySource(
        scopes=("192.0.2.0/30",),
        max_hosts_per_scope=8,
    )
    monkeypatch.setattr(
        source,
        "_port_open",
        lambda address, port: (
            address == "192.0.2.2" and port == 445
        ),
    )
    monkeypatch.setattr(
        discovery_module.socket,
        "gethostbyaddr",
        lambda address: ("newhost.local", [], [address]),
    )

    observations = source.discover()

    assert len(observations) == 1
    observation = observations[0]
    assert observation.host_id == "newhost.local"
    assert observation.platform == "unknown"
    assert observation.architecture == "unknown"
    assert observation.inside_approved_scope is True
    assert observation.trusted_bootstrap_available is False
    assert observation.observed_node_id is None


def test_unrelated_7443_listener_does_not_hide_bare_host(monkeypatch):
    source = ScopedHostPresenceDiscoverySource(
        scopes=("192.0.2.0/30",),
        max_hosts_per_scope=8,
    )
    monkeypatch.setattr(
        source,
        "_port_open",
        lambda address, port: (
            address == "192.0.2.2" and port in (445, 7443)
        ),
    )
    monkeypatch.setattr(
        discovery_module.socket,
        "gethostbyaddr",
        lambda address: ("newhost.local", [], [address]),
    )

    observations = source.discover()

    assert len(observations) == 1
    assert observations[0].host_id == "newhost.local"


def test_combined_discovery_prefers_first_source_for_same_endpoint():
    stronger = FleetDiscoveryEvidence(
        host_id="Artemis",
        hostname="artemis.local",
        platform="windows",
        architecture="amd64",
        observed_at=datetime.now(timezone.utc),
        source="mtls-agent-discovery",
        inside_approved_scope=True,
        observed_endpoint_hostname="192.0.2.2",
        observed_endpoint_port=7443,
    )
    weaker = FleetDiscoveryEvidence(
        host_id="artemis.local",
        hostname="artemis.local",
        platform="unknown",
        architecture="unknown",
        observed_at=datetime.now(timezone.utc),
        source="approved-scope-host-presence",
        inside_approved_scope=True,
        observed_endpoint_hostname="192.0.2.2",
    )

    class Source:
        def __init__(self, values):
            self.values = values
        def discover(self):
            return self.values

    result = CombinedFleetDiscoverySource(
        Source((stronger,)),
        Source((weaker,)),
    ).discover()

    assert result == (stronger,)


def test_mtls_discovery_rejects_mismatched_capability_identity(monkeypatch):
    class BadCapabilitiesConnection(FakeConnection):
        def getresponse(self):
            if self.path == "/v1/capabilities":
                return FakeResponse(
                    (
                        b'{"node_id":"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",'
                        b'"protocol_version":"1.0","capabilities":['
                        b'{"name":"system.inspect","operations":["latest"]},'
                        b'{"name":"ops.telemetry","operations":["latest"]}]}'
                    )
                )
            return super().getresponse()

    monkeypatch.setattr(
        discovery_module,
        "HTTPSConnection",
        BadCapabilitiesConnection,
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


def test_scoped_presence_discovery_can_start_without_mtls_credentials(
    monkeypatch,
):
    for name in (
        "SOFIA_REMOTE_CA",
        "SOFIA_REMOTE_CLIENT_CERT",
        "SOFIA_REMOTE_CLIENT_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    configuration = SimpleNamespace(
        fleet_discovery=SimpleNamespace(
            enabled=True,
            targets=(),
            scopes=("192.0.2.0/30",),
            max_hosts_per_scope=8,
        )
    )

    source = create_configured_fleet_discovery_source(configuration)

    assert isinstance(source, ScopedHostPresenceDiscoverySource)


def test_explicit_agent_targets_without_mtls_credentials_fail_closed(
    monkeypatch,
):
    for name in (
        "SOFIA_REMOTE_CA",
        "SOFIA_REMOTE_CLIENT_CERT",
        "SOFIA_REMOTE_CLIENT_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    configuration = SimpleNamespace(
        fleet_discovery=SimpleNamespace(
            enabled=True,
            targets=("artemis.local:7443",),
            scopes=(),
            max_hosts_per_scope=8,
        )
    )

    with pytest.raises(ValueError, match="targets require"):
        create_configured_fleet_discovery_source(configuration)
