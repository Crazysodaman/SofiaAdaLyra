"""Small authenticated HTTPS server for the Android companion."""
from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import ssl
from threading import Thread
from typing import Any, Protocol


_MAX_BODY = 64 * 1024


class _MobileHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


class MobileGatewayProtocol(Protocol):
    def ingest_sensors(self, payload: object) -> dict[str, object]: ...
    def chat(self, **kwargs: object) -> dict[str, object]: ...
    def state(self, **kwargs: object) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class MobileServerConfiguration:
    host: str = "127.0.0.1"
    port: int = 8766
    certificate: Path | None = None
    private_key: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ValueError("mobile server host is required")
        if type(self.port) is not int or not 0 <= self.port <= 65535:
            raise ValueError("mobile server port must be in 0..65535")
        if (self.certificate is None) != (self.private_key is None):
            raise ValueError("mobile TLS certificate and private key are required together")
        try:
            loopback = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            loopback = self.host.casefold() == "localhost"
        if not loopback and self.certificate is None:
            raise ValueError("non-loopback mobile server binding requires TLS")


class MobileCompanionServer:
    def __init__(
        self,
        gateway: MobileGatewayProtocol,
        *,
        token: str,
        configuration: MobileServerConfiguration = MobileServerConfiguration(),
    ) -> None:
        for method in ("ingest_sensors", "chat", "state"):
            if not callable(getattr(gateway, method, None)):
                raise TypeError("gateway must implement the mobile gateway protocol")
        if not isinstance(token, str) or not 32 <= len(token) <= 512:
            raise ValueError("mobile bearer token must contain 32..512 characters")
        if not isinstance(configuration, MobileServerConfiguration):
            raise TypeError("configuration must be MobileServerConfiguration")
        self.gateway = gateway
        self._token = token.encode("utf-8")
        outer = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SofiaMobile/1"

            def log_message(self, _format, *_args):
                return

            def _send(self, status: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(raw)

            def _authorized(self) -> bool:
                value = self.headers.get("Authorization", "")
                prefix = "Bearer "
                supplied = value[len(prefix):].encode("utf-8") if value.startswith(prefix) else b""
                return compare_digest(supplied, outer._token)

            def _json(self) -> dict[str, Any]:
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    raise ValueError("content length is required")
                length = int(raw_length)
                if not 0 < length <= _MAX_BODY:
                    raise ValueError("request body is outside supported bounds")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be an object")
                return payload

            def do_GET(self):
                if not self._authorized():
                    self._send(401, {"error": "unauthorized"})
                    return
                if self.path != "/v1/mobile/health":
                    self._send(404, {"error": "not_found"})
                    return
                self._send(200, {"status": "ready", "protocol": 1})

            def do_POST(self):
                if not self._authorized():
                    self._send(401, {"error": "unauthorized"})
                    return
                try:
                    payload = self._json()
                    if self.path == "/v1/mobile/sensors":
                        result = outer.gateway.ingest_sensors(payload)
                    elif self.path == "/v1/mobile/chat":
                        if set(payload) != {
                            "device_id", "message", "private_mode"
                        }:
                            raise ValueError("chat payload fields are invalid")
                        result = outer.gateway.chat(
                            device_id=payload["device_id"],
                            message=payload["message"],
                            private_mode=payload["private_mode"],
                        )
                    elif self.path == "/v1/mobile/state":
                        if set(payload) != {"device_id", "private_mode"}:
                            raise ValueError("state payload fields are invalid")
                        result = outer.gateway.state(
                            device_id=payload["device_id"],
                            private_mode=payload["private_mode"],
                        )
                    else:
                        self._send(404, {"error": "not_found"})
                        return
                except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                    self._send(400, {"error": "invalid_request"})
                    return
                except Exception:
                    self._send(500, {"error": "internal_error"})
                    return
                self._send(200, result)

        self._httpd = _MobileHTTPServer(
            (configuration.host, configuration.port), Handler
        )
        if configuration.certificate is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(
                str(configuration.certificate), str(configuration.private_key)
            )
            self._httpd.socket = context.wrap_socket(
                self._httpd.socket, server_side=True
            )
        self._thread: Thread | None = None

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._httpd.server_address[:2]
        return str(host), int(port)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("mobile companion server already started")
        self._thread = Thread(
            target=self._httpd.serve_forever,
            name="sofia-mobile-companion",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        self._thread = None
