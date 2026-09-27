"""Pinned mutual-TLS transport for a remote Sofía desktop conversation.

The server wraps an already-started canonical conversation service. It does not
create another Sofía runtime. A pinned client certificate is the current
single-owner authentication gate until SOCIAL principal projection is complete.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from pathlib import Path
import sqlite3
import ssl
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sofia.cognition.model import CognitiveResponse
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.distributed.tls import public_key_fingerprint_from_der_certificate


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _require_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


class RemoteChatError(RuntimeError):
    pass


class RemoteChatOutcomeUnknown(RemoteChatError):
    def __init__(self, request_id: UUID, message: str = "remote chat outcome is unknown") -> None:
        self.request_id = request_id
        super().__init__(message)


class RemoteConversation(Protocol):
    @property
    def session_id(self) -> str | None: ...
    def messages(self) -> tuple[ConversationMessage, ...]: ...
    def respond(self, content: str): ...


@dataclass(frozen=True)
class RemoteChatServerConfig:
    listen_host: str
    listen_port: int
    server_certificate: Path
    server_private_key: Path
    client_ca_file: Path
    expected_client_public_key_sha256: str
    ledger_path: Path

    def __post_init__(self) -> None:
        if not isinstance(self.listen_host, str) or not self.listen_host.strip():
            raise ValueError("listen_host required")
        if type(self.listen_port) is not int or not 1 <= self.listen_port <= 65535:
            raise ValueError("listen_port out of range")
        _require_sha256(
            self.expected_client_public_key_sha256,
            "expected client public-key SHA-256",
        )


@dataclass(frozen=True)
class RemoteChatClientConfig:
    hostname: str
    port: int
    ca_file: Path
    client_certificate: Path
    client_private_key: Path
    expected_server_public_key_sha256: str
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not isinstance(self.hostname, str) or not self.hostname.strip():
            raise ValueError("hostname required")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("port out of range")
        _require_sha256(
            self.expected_server_public_key_sha256,
            "expected server public-key SHA-256",
        )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @classmethod
    def from_endpoint(
        cls,
        endpoint: str,
        *,
        ca_file: Path,
        client_certificate: Path,
        client_private_key: Path,
        expected_server_public_key_sha256: str,
        timeout_seconds: float = 15.0,
    ) -> "RemoteChatClientConfig":
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("remote chat endpoint must be an https URL")
        return cls(
            parsed.hostname,
            parsed.port or 443,
            ca_file,
            client_certificate,
            client_private_key,
            expected_server_public_key_sha256,
            timeout_seconds,
        )


class RemoteChatLedger:
    """Durable idempotency ledger for remote respond requests."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ui_remote_chat_requests (
                        request_id TEXT PRIMARY KEY,
                        content_sha256 TEXT NOT NULL,
                        state TEXT NOT NULL CHECK(state IN ('reserved','final','outcome_unknown')),
                        response_content TEXT,
                        error_type TEXT
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def digest(content: str) -> str:
        return sha256(content.encode("utf-8")).hexdigest()

    def reserve(self, request_id: UUID, content: str) -> tuple[str, str | None] | None:
        digest = self.digest(content)
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """
                    SELECT content_sha256,state,response_content
                    FROM ui_remote_chat_requests WHERE request_id=?
                    """,
                    (str(request_id),),
                ).fetchone()
                if row is not None:
                    if row[0] != digest:
                        raise PermissionError("request ID was reused for different chat content")
                    return row[1], row[2]
                db.execute(
                    """
                    INSERT INTO ui_remote_chat_requests
                    (request_id,content_sha256,state,response_content,error_type)
                    VALUES (?,?,'reserved',NULL,NULL)
                    """,
                    (str(request_id), digest),
                )
        return None

    def finish(self, request_id: UUID, response_content: str) -> None:
        with closing(self._connect()) as db:
            with db:
                changed = db.execute(
                    """
                    UPDATE ui_remote_chat_requests
                    SET state='final',response_content=?,error_type=NULL
                    WHERE request_id=? AND state='reserved'
                    """,
                    (response_content, str(request_id)),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("remote chat request is not reserved")

    def mark_unknown(self, request_id: UUID, error_type: str) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    UPDATE ui_remote_chat_requests
                    SET state='outcome_unknown',error_type=?
                    WHERE request_id=? AND state='reserved'
                    """,
                    (error_type[:120], str(request_id)),
                )


class RemoteChatServer:
    def __init__(self, config: RemoteChatServerConfig, conversation: RemoteConversation) -> None:
        if not isinstance(config, RemoteChatServerConfig):
            raise TypeError("RemoteChatServerConfig required")
        if not hasattr(conversation, "session_id") or not callable(getattr(conversation, "messages", None)):
            raise TypeError("conversation must expose session_id and messages()")
        if not callable(getattr(conversation, "respond", None)):
            raise TypeError("conversation must expose respond(content)")
        self.config = config
        self.conversation = conversation
        self.ledger = RemoteChatLedger(config.ledger_path)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SofiaRemoteChat/1"

            def log_message(self, format, *args):
                return

            def _authorized(self) -> bool:
                cert = self.connection.getpeercert(binary_form=True)
                if not cert:
                    return False
                return (
                    public_key_fingerprint_from_der_certificate(cert)
                    == owner.config.expected_client_public_key_sha256
                )

            def _json(self, status: int, payload) -> None:
                raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _payload(self) -> dict:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise ValueError("invalid Content-Length") from exc
                if not 0 <= length <= 131072:
                    raise ValueError("request body too large")
                raw = self.rfile.read(length)
                data = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(data, dict):
                    raise ValueError("JSON object required")
                return data

            def do_GET(self):
                if not self._authorized():
                    self._json(403, {"error": "unauthorized peer"})
                    return
                session_id = owner.conversation.session_id
                if not isinstance(session_id, str) or not session_id.strip():
                    self._json(503, {"error": "conversation is not active"})
                    return
                if self.path == "/v1/session":
                    self._json(200, {"session_id": session_id})
                    return
                if self.path == "/v1/messages":
                    messages = []
                    for message in owner.conversation.messages():
                        messages.append(
                            {
                                "id": message.id,
                                "session_id": message.session_id,
                                "role": message.role.value,
                                "content": message.content,
                                "created_at": message.created_at.isoformat(),
                            }
                        )
                    self._json(200, {"session_id": session_id, "messages": messages})
                    return
                self._json(404, {"error": "not found"})

            def do_POST(self):
                if not self._authorized():
                    self._json(403, {"error": "unauthorized peer"})
                    return
                if self.path != "/v1/respond":
                    self._json(404, {"error": "not found"})
                    return
                try:
                    payload = self._payload()
                    request_id = UUID(str(payload["request_id"]))
                    content = payload["content"]
                    if not isinstance(content, str) or not content.strip() or len(content) > 64000:
                        raise ValueError("bounded nonempty content required")
                    existing = owner.ledger.reserve(request_id, content)
                    if existing is not None:
                        state, response_content = existing
                        if state == "final" and isinstance(response_content, str):
                            self._json(
                                200,
                                {
                                    "request_id": str(request_id),
                                    "outcome": "final",
                                    "content": response_content,
                                },
                            )
                        else:
                            self._json(
                                409,
                                {
                                    "request_id": str(request_id),
                                    "outcome": "outcome_unknown",
                                },
                            )
                        return
                    try:
                        response = owner.conversation.respond(content)
                        response_content = getattr(response, "content", None)
                        if not isinstance(response_content, str) or not response_content.strip():
                            raise ValueError("conversation returned empty response")
                        owner.ledger.finish(request_id, response_content)
                    except Exception as exc:
                        owner.ledger.mark_unknown(request_id, type(exc).__name__)
                        self._json(
                            500,
                            {
                                "request_id": str(request_id),
                                "outcome": "outcome_unknown",
                                "error": type(exc).__name__,
                            },
                        )
                        return
                    self._json(
                        200,
                        {
                            "request_id": str(request_id),
                            "outcome": "final",
                            "content": response_content,
                        },
                    )
                except (KeyError, TypeError, ValueError, PermissionError) as exc:
                    self._json(400, {"error": f"{type(exc).__name__}: {exc}"})

        self._server = ThreadingHTTPServer((config.listen_host, config.listen_port), Handler)
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(config.client_ca_file))
        context.load_cert_chain(
            certfile=str(config.server_certificate),
            keyfile=str(config.server_private_key),
        )
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


class PinnedRemoteConversation:
    """ConversationPort-compatible mTLS client for the desktop UITextClient."""

    def __init__(self, config: RemoteChatClientConfig) -> None:
        if not isinstance(config, RemoteChatClientConfig):
            raise TypeError("RemoteChatClientConfig required")
        self.config = config
        self._session_id: str | None = None

    def _context(self) -> ssl.SSLContext:
        context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH,
            cafile=str(self.config.ca_file),
        )
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(
            certfile=str(self.config.client_certificate),
            keyfile=str(self.config.client_private_key),
        )
        return context

    def _request(self, method: str, path: str, payload=None) -> dict:
        body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection = HTTPSConnection(
            self.config.hostname,
            self.config.port,
            context=self._context(),
            timeout=self.config.timeout_seconds,
        )
        try:
            connection.connect()
            if connection.sock is None:
                raise RemoteChatError("TLS socket unavailable")
            certificate = connection.sock.getpeercert(binary_form=True)
            if not certificate:
                raise RemoteChatError("remote runtime did not present a certificate")
            actual = public_key_fingerprint_from_der_certificate(certificate)
            if actual != self.config.expected_server_public_key_sha256:
                raise RemoteChatError("remote runtime TLS key does not match configured pin")
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            try:
                data = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RemoteChatError("remote runtime returned invalid JSON") from exc
            if response.status == 409 and isinstance(data, dict) and data.get("request_id"):
                raise RemoteChatOutcomeUnknown(UUID(data["request_id"]))
            if response.status < 200 or response.status >= 300:
                raise RemoteChatError(f"remote chat HTTP {response.status}: {str(data)[:500]}")
            if not isinstance(data, dict):
                raise RemoteChatError("remote runtime returned invalid response")
            return data
        finally:
            connection.close()

    @property
    def session_id(self) -> str:
        if self._session_id is None:
            data = self._request("GET", "/v1/session")
            value = data.get("session_id")
            if not isinstance(value, str) or not value.strip():
                raise RemoteChatError("remote runtime returned invalid session identity")
            self._session_id = value
        return self._session_id

    def messages(self) -> tuple[ConversationMessage, ...]:
        data = self._request("GET", "/v1/messages")
        result = []
        for raw in data.get("messages", ()):
            result.append(
                ConversationMessage(
                    id=str(raw["id"]),
                    session_id=str(raw["session_id"]),
                    role=ConversationRole(str(raw["role"])),
                    content=str(raw["content"]),
                    created_at=datetime.fromisoformat(str(raw["created_at"])),
                )
            )
        return tuple(result)

    def respond(self, content: str) -> CognitiveResponse:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content must be nonblank")
        request_id = uuid4()
        try:
            data = self._request(
                "POST",
                "/v1/respond",
                {"request_id": str(request_id), "content": content},
            )
        except RemoteChatOutcomeUnknown:
            raise
        except Exception as exc:
            raise RemoteChatOutcomeUnknown(
                request_id,
                "remote response may have been accepted; automatic retry is blocked",
            ) from exc
        if data.get("outcome") != "final" or not isinstance(data.get("content"), str):
            raise RemoteChatError("remote runtime returned invalid final response")
        return CognitiveResponse(data["content"])
