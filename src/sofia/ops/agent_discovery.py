"""mTLS Fleet-agent discovery against explicitly approved candidate endpoints.

This discovers agent identity evidence only. It does not approve endpoints,
enroll nodes, grant capabilities, or trust the returned identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPSConnection
import json
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
                platform=platform_name,
                architecture=architecture,
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
                platform=target.platform,
                architecture=target.architecture,
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
