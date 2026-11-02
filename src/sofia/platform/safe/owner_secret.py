"""Opt-in attended 256-bit owner secret, separate from dormant WebAuthn support.

The secret never enters argv, env, SQLite, audit payloads, model context or logs.
The stored verifier is salt + scrypt digest; successful proof is bound to one
exact action and a short lifetime. This is weaker than a hardware authenticator
on a compromised Windows machine; do not claim otherwise.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.owner_enroll_browser import require_venus_interactive_windows
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


def _secret_bytes(secret: str) -> bytes:
    if not isinstance(secret, str) or not _HEX.fullmatch(secret):
        raise PermissionError("owner secret must be exactly 64 hexadecimal characters")
    return bytes.fromhex(secret)


def _derive(secret: bytes, salt: bytes) -> bytes:
    return hashlib.scrypt(secret, salt=salt, n=2**14, r=8, p=1, dklen=32)


class OwnerSecretStore:
    """Local Windows-owner-only credential and action-bound proof store."""

    def __init__(self, state_path: Path | str):
        self.path = Path(state_path)
        self.guard = CanonicalSQLiteGuard(self.path)
        self.audit = AuditChain(self.path)
        with closing(self._db()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_owner_secret (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    windows_sid TEXT NOT NULL,
                    salt BLOB NOT NULL,
                    verifier BLOB NOT NULL,
                    version INTEGER NOT NULL CHECK(version>0),
                    enrolled_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_owner_secret_proof (
                    proof_id TEXT PRIMARY KEY,
                    action_fingerprint TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    version INTEGER NOT NULL
                )
            """)

    def _db(self) -> sqlite3.Connection:
        db = self.guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def _sid(self, *, terminal: bool = False) -> str:
        return require_venus_interactive_windows(require_terminal=terminal)

    def enabled(self) -> bool:
        with closing(self._db()) as db:
            return db.execute(
                "SELECT 1 FROM safe_owner_secret WHERE singleton=1"
            ).fetchone() is not None

    def enroll(self, secret: str) -> None:
        sid = self._sid(terminal=True)
        secret_bytes = _secret_bytes(secret)
        salt = secrets.token_bytes(32)
        digest = _derive(secret_bytes, salt)
        with closing(self._db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM safe_owner_secret WHERE singleton=1").fetchone():
                raise PermissionError("owner secret already enrolled; no silent overwrite")
            # If Windows Hello was enrolled first, preserve its pinned Windows SID.
            table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='safe_owner_host_identity'"
            ).fetchone()
            if table:
                pinned = db.execute(
                    "SELECT windows_sid FROM safe_owner_host_identity WHERE singleton=1"
                ).fetchone()
                if pinned is not None and pinned["windows_sid"] != sid:
                    raise PermissionError("Windows owner SID differs from existing enrollment")
            moment = datetime.now(timezone.utc)
            db.execute(
                "INSERT INTO safe_owner_secret "
                "(singleton,windows_sid,salt,verifier,version,enrolled_at) "
                "VALUES (1,?,?,?,?,?)",
                (sid, salt, digest, 1, moment.isoformat()),
            )
            self.audit.append_in_transaction(
                db, actor_id="Sparks", event_type="owner.secret.enrolled",
                payload={"method": "attended-venus-software-secret", "version": 1},
                occurred_at=moment, event_id="owner-secret-enrolled:" + secrets.token_hex(32),
            )

    def authenticate(self, secret: str, *, action_fingerprint: str) -> str:
        if not isinstance(action_fingerprint, str) or not re.fullmatch(
            r"[0-9a-f]{64}", action_fingerprint
        ):
            raise ValueError("exact action fingerprint required")
        sid = self._sid()
        value = _secret_bytes(secret)
        with closing(self._db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT windows_sid,salt,verifier,version FROM safe_owner_secret "
                "WHERE singleton=1"
            ).fetchone()
            if row is None or row["windows_sid"] != sid:
                raise PermissionError("software owner authentication unavailable")
            candidate = _derive(value, bytes(row["salt"]))
            if not hmac.compare_digest(candidate, bytes(row["verifier"])):
                raise PermissionError("owner authentication denied")
            moment = datetime.now(timezone.utc)
            proof_id = secrets.token_hex(32)
            db.execute(
                "INSERT INTO safe_owner_secret_proof "
                "(proof_id,action_fingerprint,verified_at,version) VALUES(?,?,?,?)",
                (proof_id, action_fingerprint, moment.isoformat(), row["version"]),
            )
            event_id = "owner-secret:" + proof_id
            self.audit.append_in_transaction(
                db, actor_id="Sparks", event_type="owner.secret.verified",
                payload={"action_fingerprint": action_fingerprint,
                         "proof_id": proof_id, "version": int(row["version"])},
                occurred_at=moment, event_id=event_id,
            )
            return event_id

    def rotate(self, old_secret: str, new_secret: str) -> None:
        sid = self._sid(terminal=True)
        old = _secret_bytes(old_secret)
        new = _secret_bytes(new_secret)
        if hmac.compare_digest(old, new):
            raise ValueError("replacement secret must be different")
        with closing(self._db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT windows_sid,salt,verifier,version FROM safe_owner_secret "
                "WHERE singleton=1"
            ).fetchone()
            if row is None or row["windows_sid"] != sid:
                raise PermissionError("owner credential unavailable")
            if not hmac.compare_digest(
                _derive(old, bytes(row["salt"])), bytes(row["verifier"])
            ):
                raise PermissionError("owner authentication denied")
            salt = secrets.token_bytes(32)
            version = int(row["version"]) + 1
            moment = datetime.now(timezone.utc)
            db.execute(
                "UPDATE safe_owner_secret SET salt=?,verifier=?,version=? WHERE singleton=1",
                (salt, _derive(new, salt), version),
            )
            self.audit.append_in_transaction(
                db, actor_id="Sparks", event_type="owner.secret.rotated",
                payload={"version": version}, occurred_at=moment,
                event_id="owner-secret-rotated:" + secrets.token_hex(32),
            )


def require_owner_approval_account(state_path: Path | str) -> str:
    """Authorize the enrolled Windows owner for approved software or WebAuthn.

    An unenrolled software secret never disables the existing WebAuthn guard.
    The host SID is verified from the Windows access token, not a username.
    """
    store = OwnerSecretStore(state_path)
    if store.enabled():
        sid = store._sid()
        with closing(store._db()) as db:
            row = db.execute(
                "SELECT windows_sid FROM safe_owner_secret WHERE singleton=1"
            ).fetchone()
            if row is None or row["windows_sid"] != sid:
                raise PermissionError("current session is not enrolled owner")
        return sid
    from sofia.platform.safe.owner_enroll_browser import require_owner_windows_account
    return require_owner_windows_account(state_path)


def _browser_secret_prompt(*, capability: str, parameters: dict,
                           fingerprint: str, timeout_seconds: int = 90) -> str:
    """Single-use loopback browser prompt for non-console desktop workers.

    This does NOT make a software secret hardware-resistant; it avoids
    touching Tk widgets from background threads and shows exact parameters.
    """
    from html import escape
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from queue import Empty, Queue
    from threading import Lock, Thread
    from urllib.parse import parse_qs, urlsplit
    import json
    import webbrowser

    nonce = secrets.token_urlsafe(32)
    submitted: Queue[str | None] = Queue(maxsize=1)
    attempt = Lock()
    consumed = [False]
    action = json.dumps(
        {"capability": capability, "parameters": parameters,
         "action_fingerprint": fingerprint},
        sort_keys=True, indent=2, allow_nan=False, ensure_ascii=False,
    )
    if len(action.encode("utf-8")) > 65_000:
        raise ValueError("approval request too long")
    html = (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Sofía private owner approval</title>"
        "<h1>Review exact action before approving</h1><pre>"
        + escape(action) + "</pre><form method='post' action='__ACTION__'>"
        "<label>Owner secret (64 hex characters):"
        "<input type='password' name='secret' autocomplete='off' "
        "minlength='64' maxlength='64' required></label>"
        "<button type='submit'>Approve this exact action</button></form>"
        "</html>"
    )
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def _valid(self, target):
            parsed = urlsplit(self.path)
            return (
                self.headers.get("Host") == f"localhost:{self.server.server_port}"
                and parsed.path == target
                and parse_qs(parsed.query).get("token") == [nonce]
            )

        def _reply(self, code, payload, content_type="text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "form-action 'self'; frame-ancestors 'none'; "
                             "base-uri 'none'")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if not self._valid("/"):
                return self._reply(404, b"Not found")
            page = html.replace("__ACTION__", "/finish?token=" + nonce).encode("utf-8")
            self._reply(200, page, "text/html; charset=utf-8")

        def do_POST(self):
            if (not self._valid("/finish")
                or self.headers.get("Origin") != f"http://localhost:{self.server.server_port}"
                or self.headers.get_content_type() != "application/x-www-form-urlencoded"):
                return self._reply(403, b"Denied")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 200:
                return self._reply(413, b"Invalid submission")
            with attempt:
                if consumed[0]:
                    return self._reply(409, b"Already attempted")
                consumed[0] = True
            try:
                body = parse_qs(
                    self.rfile.read(length).decode("ascii"), strict_parsing=True
                )
                if set(body) != {"secret"} or len(body["secret"]) != 1:
                    raise ValueError("invalid secret form")
                supplied = body["secret"][0]
                if not _HEX.fullmatch(supplied):
                    raise ValueError("invalid secret format")
                submitted.put_nowait(supplied)
                self._reply(200, b"Submitted for owner verification. Close this page.")
            except (UnicodeDecodeError, ValueError):
                submitted.put_nowait(None)
                self._reply(403, b"Authentication refused")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    worker = None
    try:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        if webbrowser.open(
            f"http://localhost:{server.server_port}/?token={nonce}"
        ) is False:
            raise RuntimeError("unable to open owner authorization browser")
        try:
            value = submitted.get(timeout=timeout_seconds)
        except Empty as exc:
            raise PermissionError("owner approval timed out") from exc
        if value is None:
            raise PermissionError("invalid owner secret submission")
        return value
    finally:
        if worker is not None:
            server.shutdown()
        server.server_close()
        if worker is not None:
            worker.join(timeout=2)


def authorize_with_secret(state_path: Path | str, *, capability: str, parameters: dict,
                          expires_seconds: int = 120):
    """Prompt locally, authenticate, then issue existing one-use SAFE approval."""
    from datetime import timedelta
    import getpass
    import sys
    from uuid import uuid4

    from sofia.platform.safe.execution_approval import (
        ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
    )

    if type(expires_seconds) is not int or not 30 <= expires_seconds <= 900:
        raise ValueError("approval TTL must be 30..900 seconds")
    store = OwnerSecretStore(state_path)
    if not store.enabled():
        raise PermissionError("owner secret not enrolled; run owner_secret_cli init")
    exact = execution_fingerprint(capability, parameters)
    # Display the action before asking for any secret. The secret must never be
    # passed as argv, placed into a GUI settings field or written to an audit.
    if sys.stdin is not None and sys.stdin.isatty():
        print("Sofía protected approval:", capability, "fingerprint:", exact)
        print("Review exact parameters:", __import__("json").dumps(
            parameters, sort_keys=True, allow_nan=False
        ))
        supplied = getpass.getpass("64-character owner secret (hidden): ")
    else:
        supplied = _browser_secret_prompt(
            capability=capability, parameters=parameters, fingerprint=exact,
        )
    if supplied is None:
        raise PermissionError("owner canceled authentication")
    event_id = store.authenticate(supplied, action_fingerprint=exact)
    moment = datetime.now(timezone.utc)
    approval = ExecutionApproval(
        approval_id=str(uuid4()), capability=capability,
        request_fingerprint=exact, approved_by="Sparks", approved_at=moment,
        expires_at=moment + timedelta(seconds=expires_seconds),
    )
    ExecutionApprovalVerifier(state_path).record(
        approval, authentication_event_id=event_id,
    )
    return approval
