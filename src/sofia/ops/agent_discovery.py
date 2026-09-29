"""mTLS Fleet-agent discovery against explicitly approved candidate endpoints.

This discovers agent identity evidence only. It does not approve endpoints,
enroll nodes, grant capabilities, or trust the returned identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPSConnection
import ipaddress
import json
import os
import socket
from pathlib import Path
import ssl
from typing import Iterable
from uuid import UUID

from sofia.distributed.tls import public_key_fingerprint_from_der_certificate
from sofia.distributed.version import FleetProtocolVersion
from sofia.ops.discovery import FleetDiscoveryEvidence


@dataclass(frozen=True, slots=True)
class AgentDiscoveryTarget:
    hostname: str
    port: int = 7443
    platform: str = "unknown"
    architecture: str = "unknown"
    inside_approved_scope: bool = False
    trusted_bootstrap_available: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.hostname, str) or not self.hostname.strip():
            raise ValueError("hostname must be nonempty")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be in 1..65535")
        for name in ("platform", "architecture"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if type(self.inside_approved_scope) is not bool:
            raise TypeError("inside_approved_scope must be boolean")
        if type(self.trusted_bootstrap_available) is not bool:
            raise TypeError("trusted_bootstrap_available must be boolean")


class MtlsAgentDiscoverySource:
    """Probe approved endpoints and convert authenticated TLS evidence to candidates.

    The client authenticates itself to the Fleet agent and verifies the agent
    certificate against the configured CA. The returned node ID/name and the
    observed server public-key fingerprint remain discovery evidence only until
    the normal durable enrollment path binds and verifies them.
    """

    def __init__(
        self,
        targets: Iterable[AgentDiscoveryTarget],
        *,
        ca_file: Path | str,
        client_certificate: Path | str,
        client_private_key: Path | str,
        timeout_seconds: float = 2.0,
        required_protocol_version: str = "1.0",
    ) -> None:
        self.targets = tuple(targets)
        if any(not isinstance(item, AgentDiscoveryTarget) for item in self.targets):
            raise TypeError("targets must contain AgentDiscoveryTarget values")
        self.ca_file = Path(ca_file)
        self.client_certificate = Path(client_certificate)
        self.client_private_key = Path(client_private_key)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = float(timeout_seconds)
        self.required_protocol = FleetProtocolVersion.parse(
            required_protocol_version
        )

    def _context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH,
            cafile=str(self.ca_file),
        )
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=str(self.client_certificate),
            keyfile=str(self.client_private_key),
        )
        return context

    def _probe(
        self,
        target: AgentDiscoveryTarget,
    ) -> FleetDiscoveryEvidence | None:
        if not target.inside_approved_scope:
            return FleetDiscoveryEvidence(
                host_id=target.hostname,
                hostname=target.hostname,
                platform=target.platform,
                architecture=target.architecture,
                observed_at=datetime.now(timezone.utc),
                source="mtls-agent-discovery",
                inside_approved_scope=False,
                trusted_bootstrap_available=target.trusted_bootstrap_available,
                observed_endpoint_hostname=target.hostname,
                observed_endpoint_port=target.port,
            )

        connection = HTTPSConnection(
            target.hostname,
            target.port,
            context=self._context(),
            timeout=self.timeout_seconds,
        )
        try:
            connection.connect()
            sock = connection.sock
            if sock is None:
                return None
            peer_cert = sock.getpeercert(binary_form=True)
            if not peer_cert:
                return None
            public_key_sha256 = public_key_fingerprint_from_der_certificate(
                peer_cert
            )
            connection.request(
                "GET",
                "/v1/identity",
                headers={"Accept": "application/json"},
            )
            response = connection.getresponse()
            raw = response.read()
            if response.status != 200:
                return None
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            if not isinstance(payload, dict):
                return None
            try:
                node_id = UUID(str(payload["node_id"]))
                name = str(payload["name"]).strip()
                protocol = FleetProtocolVersion.parse(
                    str(payload["protocol_version"])
                )
                platform_name = str(
                    payload.get("platform") or target.platform
                ).strip()
                architecture = str(
                    payload.get("architecture") or target.architecture
                ).strip()
            except (KeyError, TypeError, ValueError):
                return None
            if not name or not protocol.compatible_with(self.required_protocol):
                return None
            return FleetDiscoveryEvidence(
                host_id=name,
                hostname=target.hostname,
                platform=platform_name,
                architecture=architecture,
                observed_at=datetime.now(timezone.utc),
                source="mtls-agent-discovery",
                inside_approved_scope=True,
                trusted_bootstrap_available=target.trusted_bootstrap_available,
                installed_protocol_version=str(protocol),
                observed_node_id=node_id,
                observed_public_key_sha256=public_key_sha256,
                observed_endpoint_hostname=target.hostname,
                observed_endpoint_port=target.port,
            )
        except (OSError, ssl.SSLError):
            return None
        finally:
            connection.close()

    def discover(self) -> tuple[FleetDiscoveryEvidence, ...]:
        observations = []
        for target in self.targets:
            observation = self._probe(target)
            if observation is not None:
                observations.append(observation)
        return tuple(observations)


class ScopedMtlsAgentDiscoverySource:
    """Discover Fleet agents only inside explicitly configured network scopes."""

    def __init__(
        self,
        *,
        explicit_targets: tuple[AgentDiscoveryTarget, ...],
        scopes: tuple[str, ...],
        ca_file: Path | str,
        client_certificate: Path | str,
        client_private_key: Path | str,
        agent_port: int = 7443,
        max_hosts_per_scope: int = 256,
        connect_timeout_seconds: float = 0.2,
        mtls_timeout_seconds: float = 2.0,
    ) -> None:
        if not isinstance(explicit_targets, tuple):
            raise TypeError("explicit_targets must be a tuple")
        if not isinstance(scopes, tuple):
            raise TypeError("scopes must be a tuple")
        if type(agent_port) is not int or not 1 <= agent_port <= 65535:
            raise ValueError("agent_port must be in 1..65535")
        if (
            type(max_hosts_per_scope) is not int
            or not 1 <= max_hosts_per_scope <= 1024
        ):
            raise ValueError("max_hosts_per_scope must be in 1..1024")
        if connect_timeout_seconds <= 0 or mtls_timeout_seconds <= 0:
            raise ValueError("discovery timeouts must be positive")
        self.explicit_targets = explicit_targets
        self.scopes = scopes
        self.ca_file = Path(ca_file)
        self.client_certificate = Path(client_certificate)
        self.client_private_key = Path(client_private_key)
        self.agent_port = agent_port
        self.max_hosts_per_scope = max_hosts_per_scope
        self.connect_timeout_seconds = float(connect_timeout_seconds)
        self.mtls_timeout_seconds = float(mtls_timeout_seconds)

    def _scope_addresses(self) -> tuple[str, ...]:
        addresses: list[str] = []
        for raw in self.scopes:
            try:
                network = ipaddress.ip_network(raw, strict=False)
            except ValueError as exc:
                raise ValueError(
                    f"invalid Fleet discovery scope: {raw}"
                ) from exc
            hosts = tuple(str(value) for value in network.hosts())
            if len(hosts) > self.max_hosts_per_scope:
                raise ValueError(
                    "Fleet discovery scope exceeds max_hosts_per_scope: "
                    f"{raw} has {len(hosts)} hosts"
                )
            addresses.extend(hosts)
        return tuple(dict.fromkeys(addresses))

    def _reachable(self, address: str) -> AgentDiscoveryTarget | None:
        try:
            with socket.create_connection(
                (address, self.agent_port),
                timeout=self.connect_timeout_seconds,
            ):
                pass
        except OSError:
            return None
        try:
            hostname = socket.gethostbyaddr(address)[0]
        except (OSError, socket.herror):
            hostname = address
        return AgentDiscoveryTarget(
            hostname=hostname,
            port=self.agent_port,
            inside_approved_scope=True,
        )

    def discover(self) -> tuple[FleetDiscoveryEvidence, ...]:
        candidates = list(self.explicit_targets)
        addresses = self._scope_addresses()
        if addresses:
            workers = min(32, len(addresses))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for target in pool.map(self._reachable, addresses):
                    if target is not None:
                        candidates.append(target)
        unique = {
            (target.hostname.casefold(), target.port): target
            for target in candidates
        }
        source = MtlsAgentDiscoverySource(
            tuple(unique.values()),
            ca_file=self.ca_file,
            client_certificate=self.client_certificate,
            client_private_key=self.client_private_key,
            timeout_seconds=self.mtls_timeout_seconds,
        )
        return source.discover()


def _parse_discovery_target(value: str) -> AgentDiscoveryTarget:
    raw = value.strip()
    if not raw:
        raise ValueError("Fleet discovery target must be nonempty")
    if raw.count(":") > 1:
        raise ValueError(
            "Fleet discovery target must use hostname or hostname:port"
        )
    if ":" in raw:
        hostname, port_text = raw.rsplit(":", 1)
        if not port_text.isdigit():
            raise ValueError("Fleet discovery target port must be numeric")
        port = int(port_text)
    else:
        hostname = raw
        port = 7443
    return AgentDiscoveryTarget(
        hostname=hostname,
        port=port,
        inside_approved_scope=True,
    )


def create_configured_fleet_discovery_source(configuration):
    policy = configuration.fleet_discovery
    if not policy.enabled:
        return None
    if not policy.targets and not policy.scopes:
        raise ValueError(
            "Fleet discovery is enabled but no approved targets or scopes "
            "are configured"
        )
    values = {
        "ca": os.environ.get("SOFIA_REMOTE_CA", "").strip(),
        "cert": os.environ.get("SOFIA_REMOTE_CLIENT_CERT", "").strip(),
        "key": os.environ.get("SOFIA_REMOTE_CLIENT_KEY", "").strip(),
    }
    if not all(values.values()):
        raise ValueError(
            "Fleet discovery requires SOFIA_REMOTE_CA, "
            "SOFIA_REMOTE_CLIENT_CERT and SOFIA_REMOTE_CLIENT_KEY"
        )
    return ScopedMtlsAgentDiscoverySource(
        explicit_targets=tuple(
            _parse_discovery_target(value)
            for value in policy.targets
        ),
        scopes=policy.scopes,
        ca_file=Path(values["ca"]),
        client_certificate=Path(values["cert"]),
        client_private_key=Path(values["key"]),
        max_hosts_per_scope=policy.max_hosts_per_scope,
    )
