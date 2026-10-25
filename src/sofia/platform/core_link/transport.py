"""Pinned mutual-TLS transport for the Core Link SDK contract.

The certificate is the only client identity accepted by the host.  Request
JSON deliberately contains no principal, audience, grant, or credential.
Client secrets are resolved from the Platform secret owner at connection time
and are never written to the Core Link binding registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
from threading import BoundedSemaphore
from typing import Callable, TYPE_CHECKING

from sofia.platform.core_link.binding import (
    CoreLinkBinding, CoreLinkBindingState, CoreLinkBindingStore,
)
from sofia.platform.distributed.tls import (
    public_key_fingerprint_from_der_certificate,
)
from sofia.sdk.core_link import (
    CoreLinkRequest, CoreLinkResponse, CoreLinkResponseStatus,
)

if TYPE_CHECKING:
    from sofia.platform.core_link.conversation import CoreLinkConversationGateway


_FP = re.compile(r"^[0-9a-f]{64}$")
_MAX_WIRE_BYTES = 72 * 1024


class CoreLinkTransportError(RuntimeError):
    """A request could not be authenticated or completed by the transport."""


@dataclass(frozen=True, slots=True)
class CoreLinkTLSCredentials:
    ca_file: Path
    client_certificate: Path
    client_private_key: Path

    def __post_init__(self) -> None:
        for name in ("ca_file", "client_certificate", "client_private_key"):
            if not isinstance(getattr(self, name), Path):
                raise TypeError(f"{name} must be a Path")


@dataclass(frozen=True, slots=True)
class CoreLinkEndpoint:
    endpoint_id: str
    hostname: str
    port: int

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint_id, str) or not self.endpoint_id.strip():
            raise ValueError("endpoint_id required")
        if not isinstance(self.hostname, str) or not self.hostname.strip():
            raise ValueError("hostname required")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port must be in 1..65535")


@dataclass(frozen=True, slots=True)
class CoreLinkServerConfiguration:
    listen_host: str
    listen_port: int
    server_certificate: Path
    server_private_key: Path
    client_ca_file: Path
    max_inflight_requests: int = 16
    socket_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not isinstance(self.listen_host, str) or not self.listen_host.strip():
            raise ValueError("listen_host required")
        if type(self.listen_port) is not int or not 0 <= self.listen_port <= 65535:
            raise ValueError("listen_port must be in 0..65535")
        for name in ("server_certificate", "server_private_key", "client_ca_file"):
            if not isinstance(getattr(self, name), Path):
                raise TypeError(f"{name} must be a Path")
        if type(self.max_inflight_requests) is not int or not (
            1 <= self.max_inflight_requests <= 256
        ):
            raise ValueError("max_inflight_requests must be in 1..256")
        if not 0 < self.socket_timeout_seconds <= 300:
            raise ValueError("socket_timeout_seconds must be in (0, 300]")


class CoreLinkServer:
    """Bounded mTLS HTTP adapter around the canonical conversation gateway."""

    def __init__(
        self, configuration: CoreLinkServerConfiguration,
        gateway: "CoreLinkConversationGateway",
    ) -> None:
        if not isinstance(configuration, CoreLinkServerConfiguration):
            raise TypeError("configuration must be CoreLinkServerConfiguration")
        if not callable(getattr(gateway, "dispatch", None)) or not callable(
            getattr(gateway, "close", None)
        ):
            raise TypeError("gateway must expose dispatch() and close()")
        self.configuration = configuration
        self.gateway = gateway
        self._capacity = BoundedSemaphore(configuration.max_inflight_requests)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "CompanionCoreLink/1"

            def log_message(self, format, *args):
                return

            def _json(self, status: int, payload: object) -> None:
                body = json.dumps(
                    payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _fingerprint(self) -> str:
                certificate = self.connection.getpeercert(binary_form=True)
                if not certificate:
                    raise PermissionError("client certificate required")
                return public_key_fingerprint_from_der_certificate(certificate)

            def _read_request(self) -> CoreLinkRequest:
                raw_length = self.headers.get("Content-Length", "")
                try:
                    length = int(raw_length)
                except ValueError as exc:
                    raise ValueError("invalid Content-Length") from exc
                if not 1 <= length <= _MAX_WIRE_BYTES:
                    raise ValueError("Core Link request body size is invalid")
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("Core Link request is not valid JSON") from exc
                return CoreLinkRequest.from_payload(payload)

            def do_POST(self) -> None:
                if self.path != "/v1/core-link":
                    self._json(404, {"error": "not found"})
                    return
                if not owner._capacity.acquire(blocking=False):
                    self._json(503, {"error": "Core Link request capacity exhausted"})
                    return
                request = None
                try:
                    self.connection.settimeout(
                        owner.configuration.socket_timeout_seconds
                    )
                    fingerprint = self._fingerprint()
                    request = self._read_request()
                    response = owner.gateway.dispatch(
                        certificate_public_key_sha256=fingerprint,
                        request=request,
                    )
                    self._json(200, response.to_payload())
                except PermissionError as exc:
                    if request is None:
                        self._json(403, {"error": str(exc)})
                    else:
                        response = CoreLinkResponse(
                            request.request_id, CoreLinkResponseStatus.DENIED,
                            {"error": str(exc)}, datetime.now(timezone.utc),
                        )
                        self._json(403, response.to_payload())
                except (TypeError, ValueError) as exc:
                    self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
                except Exception as exc:
                    if request is None:
                        self._json(500, {"error": "Core Link request failed"})
                    else:
                        response = CoreLinkResponse(
                            request.request_id, CoreLinkResponseStatus.FAILED,
                            {"error": type(exc).__name__},
                            datetime.now(timezone.utc),
                        )
                        self._json(500, response.to_payload())
                finally:
                    owner._capacity.release()

        class BoundedThreadingHTTPServer(ThreadingHTTPServer):
            daemon_threads = True

        self._server = BoundedThreadingHTTPServer(
            (configuration.listen_host, configuration.listen_port), Handler,
        )
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(configuration.client_ca_file))
        context.load_cert_chain(
            certfile=str(configuration.server_certificate),
            keyfile=str(configuration.server_private_key),
        )
        self._server.socket = context.wrap_socket(
            self._server.socket, server_side=True,
        )

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self.gateway.close()


class PinnedCoreLinkClient:
    """Core-free SDK client pinned to one explicitly selected binding."""

    def __init__(
        self, binding_store: CoreLinkBindingStore, *,
        endpoint_resolver: Callable[[str], CoreLinkEndpoint | None],
        credential_resolver: Callable[[str], CoreLinkTLSCredentials],
        timeout_seconds: float = 30.0,
    ) -> None:
        if not isinstance(binding_store, CoreLinkBindingStore):
            raise TypeError("binding_store must be CoreLinkBindingStore")
        if not callable(endpoint_resolver) or not callable(credential_resolver):
            raise TypeError("endpoint and credential resolvers must be callable")
        if not 0 < timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be in (0, 300]")
        self.binding_store = binding_store
        self.endpoint_resolver = endpoint_resolver
        self.credential_resolver = credential_resolver
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _context(credentials: CoreLinkTLSCredentials) -> ssl.SSLContext:
        context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=str(credentials.ca_file),
        )
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=str(credentials.client_certificate),
            keyfile=str(credentials.client_private_key),
        )
        return context

    def _selected(self, request: CoreLinkRequest) -> tuple[CoreLinkBinding, CoreLinkEndpoint]:
        snapshot = self.binding_store.load()
        binding = snapshot.selected()
        if binding is None:
            raise CoreLinkTransportError("no Core Link binding is explicitly selected")
        if binding.state is not CoreLinkBindingState.ACTIVE:
            raise CoreLinkTransportError("selected Core Link binding is not active")
        exact = (
            request.local_platform_id == binding.local_platform_id
            and request.remote_platform_id == binding.remote_platform_id
            and request.remote_core_identity_id == binding.remote_core_identity_id
            and request.remote_core_generation == binding.remote_core_generation
            and request.protocol == binding.protocol_version
        )
        if not exact:
            raise CoreLinkTransportError("request does not match selected Core binding")
        endpoint = self.endpoint_resolver(binding.endpoint_id)
        if endpoint is None or endpoint.endpoint_id != binding.endpoint_id:
            raise CoreLinkTransportError("selected Core endpoint is unavailable")
        return binding, endpoint

    def request(self, request: CoreLinkRequest) -> CoreLinkResponse:
        if not isinstance(request, CoreLinkRequest):
            raise TypeError("request must be CoreLinkRequest")
        binding, endpoint = self._selected(request)
        credentials = self.credential_resolver(binding.credential_ref)
        if not isinstance(credentials, CoreLinkTLSCredentials):
            raise CoreLinkTransportError("credential resolver returned invalid credentials")
        body = json.dumps(
            request.to_payload(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        connection = HTTPSConnection(
            endpoint.hostname, endpoint.port,
            context=self._context(credentials), timeout=self.timeout_seconds,
        )
        try:
            connection.connect()
            socket = connection.sock
            if socket is None:
                raise CoreLinkTransportError("Core Link TLS socket unavailable")
            certificate = socket.getpeercert(binary_form=True)
            if not certificate:
                raise CoreLinkTransportError("Core Link host certificate missing")
            observed = public_key_fingerprint_from_der_certificate(certificate)
            expected = binding.trust_anchor_ref.removeprefix("sha256:")
            if _FP.fullmatch(expected) is None or observed != expected:
                raise CoreLinkTransportError("Core Link host public key pin mismatch")
            connection.request(
                "POST", "/v1/core-link", body=body,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            http_response = connection.getresponse()
            raw = http_response.read(_MAX_WIRE_BYTES + 1)
            if len(raw) > _MAX_WIRE_BYTES:
                raise CoreLinkTransportError("Core Link response exceeds size limit")
            try:
                payload = json.loads(raw.decode("utf-8"))
                response = CoreLinkResponse.from_payload(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise CoreLinkTransportError(
                    f"Core Link host returned invalid HTTP {http_response.status} response"
                ) from exc
            if response.request_id != request.request_id:
                raise CoreLinkTransportError("Core Link response request identity mismatch")
            if response.protocol != binding.protocol_version:
                raise CoreLinkTransportError("Core Link response protocol mismatch")
            return response
        except (OSError, ssl.SSLError) as exc:
            raise CoreLinkTransportError("Core Link connection failed") from exc
        finally:
            connection.close()
