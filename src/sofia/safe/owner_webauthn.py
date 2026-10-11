"""Action-bound WebAuthn/FIDO2 assertion verifier; no self-enrollment backdoor.

Windows Hello platform passkeys and physical FIDO2 keys use this protocol.
Enrollment MUST be independently operator-authenticated; registering a new key
based on a supplied actor string would destroy the trust boundary.
"""
from __future__ import annotations

import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.audit import AuditChain
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str, *, limit: int = 8192) -> bytes:
    if not isinstance(value, str) or not value or len(value) > limit * 2:
        raise PermissionError("invalid assertion field")
    try:
        raw = base64.b64decode(
            value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise PermissionError("invalid base64url assertion field") from exc
    if len(raw) > limit or _b64(raw) != value:
        raise PermissionError("noncanonical or oversized assertion field")
    return raw


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware time required")
    return value.astimezone(timezone.utc)


def ensure_owner_webauthn_schema(db: sqlite3.Connection) -> None:
    """Idempotent canonical schema shared by runtime SAFE and enrollment.

    A never-enrolled application must be able to inspect ordinary approvals
    without missing-table errors; no keys are enrolled by this schema creation.
    """
    db.execute("""
        CREATE TABLE IF NOT EXISTS safe_owner_credential (
            credential_id TEXT PRIMARY KEY,
            public_key_der BLOB NOT NULL,
            credential_kind TEXT NOT NULL CHECK(credential_kind IN ('platform','security_key')),
            sign_count INTEGER NOT NULL CHECK(sign_count >= 0),
            enrolled_at TEXT NOT NULL,
            revoked_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS safe_owner_challenge (
            challenge_digest TEXT PRIMARY KEY,
            credential_id TEXT NOT NULL,
            action_fingerprint TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            consumed_at TEXT,
            FOREIGN KEY(credential_id) REFERENCES safe_owner_credential(credential_id)
        )
    """)


class OwnerWebAuthnVerifier:
    """Verify one-use registered ES256 assertion and commit replay/audit atomically."""

    def __init__(self, state_path: Path | str, *, rp_id: str, origin: str):
        uri = urlsplit(origin)
        if (
            not rp_id or len(rp_id) > 253 or uri.hostname != rp_id
            or uri.path or uri.query or uri.fragment or uri.username
            or uri.password or uri.scheme not in ("http", "https")
            or (uri.scheme == "http" and rp_id != "localhost")
            or uri.geturl() != origin
        ):
            raise ValueError("reviewed exact RP ID and origin required")
        self.rp_id, self.origin = rp_id, origin
        self._guard = CanonicalSQLiteGuard(state_path)
        self.audit = AuditChain(state_path)
        with closing(self._db()) as db, db:
            ensure_owner_webauthn_schema(db)

    def _db(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def issue(self, *, credential_id: str, action_fingerprint: str,
              now: datetime | None = None, ttl_seconds: int = 90) -> dict:
        if type(ttl_seconds) is not int or not 15 <= ttl_seconds <= 120:
            raise ValueError("challenge must expire within 15..120 seconds")
        if not isinstance(action_fingerprint, str) or len(action_fingerprint) != 64 or any(
            x not in "0123456789abcdef" for x in action_fingerprint
        ):
            raise ValueError("exact action fingerprint required")
        _unb64(credential_id, limit=1024)
        moment = _utc(now or datetime.now(timezone.utc))
        challenge = _b64(secrets.token_bytes(32))
        digest = sha256(challenge.encode("ascii")).hexdigest()
        with closing(self._db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT credential_kind FROM safe_owner_credential "
                "WHERE credential_id=? AND revoked_at IS NULL", (credential_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("no independently enrolled active credential")
            db.execute(
                "INSERT INTO safe_owner_challenge "
                "(challenge_digest,credential_id,action_fingerprint,issued_at,expires_at) "
                "VALUES(?,?,?,?,?)",
                (digest, credential_id, action_fingerprint, moment.isoformat(),
                 (moment + timedelta(seconds=ttl_seconds)).isoformat()),
            )
        return {"challenge": challenge, "rp_id": self.rp_id,
                "allow_credentials": [credential_id], "user_verification": "required",
                "expires_at": (moment + timedelta(seconds=ttl_seconds)).isoformat(),
                "credential_kind": row["credential_kind"]}

    def verify(self, *, challenge: str, credential_id: str, action_fingerprint: str,
               client_data_json: str, authenticator_data: str, signature: str,
               security_key_required: bool, now: datetime | None = None) -> dict:
        if type(security_key_required) is not bool:
            raise TypeError("security_key_required must be bool")
        if len(_unb64(challenge, limit=64)) != 32:
            raise PermissionError("challenge must be 32 bytes")
        raw_client = _unb64(client_data_json)
        auth = _unb64(authenticator_data, limit=4096)
        sig = _unb64(signature, limit=4096)
        if len(auth) < 37:
            raise PermissionError("WebAuthn authenticator data too short")
        try:
            client = json.loads(raw_client)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PermissionError("invalid clientDataJSON") from exc
        if (
            not isinstance(client, dict)
            or client.get("type") != "webauthn.get"
            or client.get("challenge") != challenge
            or client.get("origin") != self.origin
            or client.get("crossOrigin", False) is not False
            or auth[:32] != sha256(self.rp_id.encode("utf-8")).digest()
            or not (auth[32] & 1) or not (auth[32] & 4) or (auth[32] & 64)
        ):
            raise PermissionError("WebAuthn origin, RP, challenge, UP or UV mismatch")
        count = int.from_bytes(auth[33:37], "big")
        moment = _utc(now or datetime.now(timezone.utc))
        digest = sha256(challenge.encode("ascii")).hexdigest()
        with closing(self._db()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT ch.credential_id,ch.action_fingerprint,ch.issued_at,ch.expires_at,"
                "ch.consumed_at,cr.credential_kind,cr.public_key_der,cr.sign_count,"
                "cr.revoked_at FROM safe_owner_challenge ch JOIN safe_owner_credential cr "
                "ON cr.credential_id=ch.credential_id WHERE ch.challenge_digest=?",
                (digest,),
            ).fetchone()
            if (
                row is None or row["consumed_at"] is not None or row["revoked_at"] is not None
                or row["credential_id"] != credential_id
                or row["action_fingerprint"] != action_fingerprint
                or not datetime.fromisoformat(row["issued_at"]) <= moment <
                    datetime.fromisoformat(row["expires_at"])
                or (security_key_required and row["credential_kind"] != "security_key")
            ):
                raise PermissionError("unknown, expired, wrong-scope or used owner challenge")
            old_count = int(row["sign_count"])
            if count and old_count and count <= old_count:
                raise PermissionError("authenticator counter replay")
            try:
                key = serialization.load_der_public_key(bytes(row["public_key_der"]))
                if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
                    raise PermissionError("only ES256 P-256 enrolled credentials supported")
                key.verify(sig, auth + sha256(raw_client).digest(),
                           ec.ECDSA(hashes.SHA256()))
            except (InvalidSignature, ValueError, TypeError) as exc:
                raise PermissionError("WebAuthn signature invalid") from exc
            updated = db.execute(
                "UPDATE safe_owner_challenge SET consumed_at=? "
                "WHERE challenge_digest=? AND consumed_at IS NULL",
                (moment.isoformat(), digest),
            )
            if updated.rowcount != 1:
                raise PermissionError("owner challenge already consumed")
            if count:
                db.execute(
                    "UPDATE safe_owner_credential SET sign_count=? WHERE credential_id=?",
                    (count, credential_id),
                )
            event_id = "owner-webauthn:" + digest
            self.audit.append_in_transaction(
                db, actor_id="Sparks", event_type="owner.webauthn.verified",
                payload={"credential_id_sha256": sha256(credential_id.encode()).hexdigest(),
                         "action_fingerprint": action_fingerprint,
                         "credential_kind": row["credential_kind"],
                         "challenge_digest": digest},
                occurred_at=moment, event_id=event_id,
            )
        return {"authentication_event_id": event_id,
                "action_fingerprint": action_fingerprint,
                "credential_kind": row["credential_kind"]}
