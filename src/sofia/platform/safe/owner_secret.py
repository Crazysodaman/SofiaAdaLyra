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
        import tkinter as tk
        from tkinter import messagebox, simpledialog
        root = tk._default_root
        temporary = root is None
        if temporary:
            root = tk.Tk()
            root.withdraw()
        try:
            if not messagebox.askyesno(
                "Sofía protected approval",
                f"Approve ONE action?\n{capability}\nExact fingerprint:\n{exact}",
                parent=root,
            ):
                raise PermissionError("owner declined protected approval")
            supplied = simpledialog.askstring(
                "Sofía owner secret", "Enter the 64-character owner secret:",
                parent=root, show="*",
            )
        finally:
            if temporary:
                root.destroy()
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
