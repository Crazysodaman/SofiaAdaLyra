"""Operator-controlled, independently authenticated mobile device credentials.

A mobile bearer is a high-entropy random capability belonging to ONE enrolled
device. Only a SHA-256 verifier is persisted in canonical sofia.db. Tokens are
not accepted as authority to enroll, rotate or revoke another device.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from pathlib import Path
import re
import secrets
import sqlite3
import sys

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard

_DEVICE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TOKEN = re.compile(r"sm1_[A-Za-z0-9_-]{48,128}\Z")


@dataclass(frozen=True, slots=True)
class EnrolledDevice:
    device_id: str
    status: str
    generation: int
    issued_at: str
    revoked_at: str | None


class MobileDeviceCredentialStore:
    """One credential per device. SQLite is the only durable authority."""

    def __init__(self, state_path: Path | str) -> None:
        self.state_path = Path(state_path)
        # The credential authority cannot silently follow a swapped database.
        self._state_guard = CanonicalSQLiteGuard(self.state_path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mobile_device_credential (
                    device_id TEXT PRIMARY KEY,
                    token_sha256 TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN ('active','revoked')),
                    generation INTEGER NOT NULL CHECK(generation >= 1),
                    issued_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE TABLE IF NOT EXISTS mobile_device_credential_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    action TEXT NOT NULL
                        CHECK(action IN ('enrolled','rotated','revoked')),
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL CHECK(actor='local-operator')
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = self._state_guard.connect(timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _device(device_id: str) -> str:
        if not isinstance(device_id, str) or not _DEVICE.fullmatch(device_id):
            raise ValueError("device_id must be a bounded registered device identifier")
        return device_id

    @staticmethod
    def _digest(token: str) -> str | None:
        if not isinstance(token, str) or not _TOKEN.fullmatch(token):
            return None
        return sha256(token.encode("ascii")).hexdigest()

    def authenticate(self, token: str) -> str | None:
        """Resolve caller identity from secret, never from request JSON."""
        fingerprint = self._digest(token)
        if fingerprint is None:
            return None
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT device_id,token_sha256 FROM mobile_device_credential "
                "WHERE token_sha256=? AND status='active'",
                (fingerprint,),
            ).fetchone()
        if row is None or not hmac.compare_digest(row[1], fingerprint):
            return None
        return row[0]

    def active_generation(self, device_id: str) -> int | None:
        """Return canonical current device binding epoch, if still enrolled."""
        self._device(device_id)
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT generation FROM mobile_device_credential "
                "WHERE device_id=? AND status='active'", (device_id,),
            ).fetchone()
        return None if row is None else int(row[0])

    def active_count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute(
                "SELECT COUNT(*) FROM mobile_device_credential WHERE status='active'"
            ).fetchone()[0])

    def list_devices(self) -> tuple[EnrolledDevice, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT device_id,status,generation,issued_at,revoked_at "
                "FROM mobile_device_credential ORDER BY device_id"
            ).fetchall()
        return tuple(EnrolledDevice(*row) for row in rows)

    def enroll(self, device_id: str, *, rotate: bool = False) -> str:
        """Operator-only call; return a new bearer exactly once, never store it."""
        self._device(device_id)
        if type(rotate) is not bool:
            raise TypeError("rotate must be an explicit boolean")
        token = "sm1_" + secrets.token_urlsafe(48)
        digest = self._digest(token)
        if digest is None:
            raise RuntimeError("failed to generate a valid pairing credential")
        stamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT generation,status FROM mobile_device_credential WHERE device_id=?",
                (device_id,),
            ).fetchone()
            if row is not None and not rotate:
                raise PermissionError(
                    "device already enrolled or revoked; explicit --rotate required"
                )
            generation = 1 if row is None else int(row[0]) + 1
            action = "enrolled" if row is None else "rotated"
            if row is None:
                db.execute(
                    "INSERT INTO mobile_device_credential VALUES(?,?,'active',?,?,NULL)",
                    (device_id, digest, generation, stamp),
                )
            else:
                db.execute(
                    "UPDATE mobile_device_credential SET token_sha256=?,status='active',"
                    "generation=?,issued_at=?,revoked_at=NULL WHERE device_id=?",
                    (digest, generation, stamp, device_id),
                )
            db.execute(
                "INSERT INTO mobile_device_credential_audit "
                "(device_id,generation,action,occurred_at,actor) "
                "VALUES(?,?,?,?,'local-operator')",
                (device_id, generation, action, stamp),
            )
        return token

    def revoke(self, device_id: str) -> bool:
        self._device(device_id)
        stamp = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT generation,status FROM mobile_device_credential WHERE device_id=?",
                (device_id,),
            ).fetchone()
            if row is None or row[1] == "revoked":
                return False
            db.execute(
                "UPDATE mobile_device_credential SET status='revoked',revoked_at=? "
                "WHERE device_id=? AND status='active'",
                (stamp, device_id),
            )
            db.execute(
                "INSERT INTO mobile_device_credential_audit "
                "(device_id,generation,action,occurred_at,actor) "
                "VALUES(?,?,'revoked',?,'local-operator')",
                (device_id, int(row[0]), stamp),
            )
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.mobile",
        description="LOCAL OPERATOR command; never a remote pairing endpoint.",
    )
    parser.add_argument("--state-path", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    enroll = commands.add_parser("enroll")
    enroll.add_argument("--device-id", required=True)
    enroll.add_argument("--rotate", action="store_true")
    enroll.add_argument("--owner-approved", action="store_true", required=True)
    revoke = commands.add_parser("revoke")
    revoke.add_argument("--device-id", required=True)
    revoke.add_argument("--owner-approved", action="store_true", required=True)
    commands.add_parser("list")
    args = parser.parse_args(argv)
    try:
        store = MobileDeviceCredentialStore(args.state_path)
        if args.action == "enroll":
            token = store.enroll(args.device_id, rotate=args.rotate)
            # The owner deliberately requested a credential at the physical
            # console. Never print in list, logs, SQL or diagnostics.
            print(f"Enrolled device: {args.device_id}")
            print(f"Pairing token (copy securely now; never shown again): {token}")
        elif args.action == "revoke":
            print("Revoked" if store.revoke(args.device_id) else "Already absent/revoked")
        else:
            for item in store.list_devices():
                print(f"{item.device_id}\t{item.status}\tgeneration={item.generation}")
        return 0
    except (OSError, sqlite3.Error, ValueError, PermissionError, RuntimeError) as exc:
        print(f"Mobile pairing denied: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
