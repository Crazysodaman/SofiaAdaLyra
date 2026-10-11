"""Strict WebAuthn ES256 registration parsing and durable owner key management.

Registration evidence is checked here; independent authority to enroll is
checked by the attended Windows owner enrollment ceremony. Format "none" is
NOT hardware attestation. A "security_key" role is supervised operator
classification and must never be described as manufacturer-attested.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier, _b64, _unb64, _utc


def _cbor(data: bytes, offset: int = 0, depth: int = 0) -> tuple[object, int]:
    """Strict finite CBOR subset for CTAP ES256 COSE keys and fmt=none."""
    if depth > 12 or offset >= len(data):
        raise PermissionError("invalid CBOR nesting or truncation")
    initial = data[offset]
    offset += 1
    major, ai = initial >> 5, initial & 31
    if ai < 24:
        n = ai
    elif ai in (24, 25, 26):
        count = {24: 1, 25: 2, 26: 4}[ai]
        if offset + count > len(data):
            raise PermissionError("truncated CBOR length")
        n = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    else:
        raise PermissionError("indefinite, tagged or 64-bit CBOR not permitted")
    if n > 65536:
        raise PermissionError("CBOR item exceeds bound")
    if major == 0:
        return n, offset
    if major == 1:
        return -1 - n, offset
    if major in (2, 3):
        if offset + n > len(data):
            raise PermissionError("truncated CBOR bytes")
        raw = data[offset:offset + n]
        if major == 2:
            return raw, offset + n
        try:
            return raw.decode("utf-8"), offset + n
        except UnicodeDecodeError as exc:
            raise PermissionError("invalid CBOR text") from exc
    if major == 4:
        if n > 128:
            raise PermissionError("oversized CBOR array")
        items = []
        for _ in range(n):
            item, offset = _cbor(data, offset, depth + 1)
            items.append(item)
        return items, offset
    if major == 5:
        if n > 128:
            raise PermissionError("oversized CBOR map")
        items = {}
        for _ in range(n):
            key, offset = _cbor(data, offset, depth + 1)
            if type(key) not in (str, int) or key in items:
                raise PermissionError("duplicate or invalid CBOR key")
            item, offset = _cbor(data, offset, depth + 1)
            items[key] = item
        return items, offset
    raise PermissionError("unsupported CBOR primitive")


def _complete_cbor(data: bytes) -> object:
    if len(data) > 16384:
        raise PermissionError("oversized CBOR input")
    value, end = _cbor(data)
    if end != len(data):
        raise PermissionError("trailing CBOR content")
    return value


def parse_registration(
    *, client_data_json: str, attestation_object: str, expected_challenge: str,
    expected_origin: str, rp_id: str,
) -> tuple[str, bytes, int]:
    """Return verified registration credential ID, ES256 public DER, counter.

    Strictly checks CTAP/WebAuthn registration structure, RP hash and UV.
    No manufacturer attestation is accepted or claimed.
    """
    raw_client = _unb64(client_data_json, limit=8192)
    try:
        client = json.loads(raw_client)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PermissionError("malformed WebAuthn registration client data") from exc
    if (
        not isinstance(client, dict) or client.get("type") != "webauthn.create"
        or client.get("challenge") != expected_challenge
        or client.get("origin") != expected_origin
        or client.get("crossOrigin", False) is not False
    ):
        raise PermissionError("registration challenge, type or origin mismatch")
    obj = _complete_cbor(_unb64(attestation_object, limit=16384))
    if (
        not isinstance(obj, dict) or set(obj) != {"fmt", "attStmt", "authData"}
        or obj["fmt"] != "none" or obj["attStmt"] != {}
        or type(obj["authData"]) is not bytes
    ):
        raise PermissionError("only non-attested WebAuthn registration is supported")
    auth = obj["authData"]
    if len(auth) < 55 or auth[:32] != sha256(rp_id.encode("utf-8")).digest():
        raise PermissionError("registration RP hash or authData invalid")
    flags = auth[32]
    if flags & 0x45 != 0x45 or flags & 0x80:
        raise PermissionError("registration requires UP, UV, AT and no extensions")
    count = int.from_bytes(auth[33:37], "big")
    identifier_len = int.from_bytes(auth[53:55], "big")
    if not 1 <= identifier_len <= 1024 or len(auth) <= 55 + identifier_len:
        raise PermissionError("malformed WebAuthn credential ID")
    raw_id = auth[55:55 + identifier_len]
    cose = _complete_cbor(auth[55 + identifier_len:])
    if (
        not isinstance(cose, dict)
        or set(cose) != {1, 3, -1, -2, -3}
        or cose[1] != 2 or cose[3] != -7 or cose[-1] != 1
        or type(cose[-2]) is not bytes or type(cose[-3]) is not bytes
        or len(cose[-2]) != 32 or len(cose[-3]) != 32
    ):
        raise PermissionError("only a complete ES256 P-256 COSE public key is supported")
    try:
        public = ec.EllipticCurvePublicNumbers(
            int.from_bytes(cose[-2], "big"),
            int.from_bytes(cose[-3], "big"), ec.SECP256R1(),
        ).public_key()
    except ValueError as exc:
        raise PermissionError("invalid P-256 public key point") from exc
    der = public.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return _b64(raw_id), der, count


def persist_enrollment(
    verifier: OwnerWebAuthnVerifier, *, credential_id: str,
    public_key_der: bytes, count: int, kind: str,
    first: bool, authorizing_event_id: str | None,
    registration_challenge_digest: str,
    at: datetime | None = None,
) -> None:
    """Write an attended credential after verified WebAuthn registration.

    For later keys, require an independently consumed authenticated proof
    and ensure the receipt cannot authorize a second enrollment.
    """
    if not isinstance(verifier, OwnerWebAuthnVerifier):
        raise TypeError("canonical WebAuthn verifier required")
    if kind not in ("platform", "security_key") or type(first) is not bool:
        raise ValueError("approved credential role required")
    if first and kind != "platform":
        raise PermissionError("first enrollment must be Windows Hello")
    if not isinstance(count, int) or count < 0:
        raise ValueError("invalid authenticator counter")
    _unb64(credential_id, limit=1024)
    if not isinstance(registration_challenge_digest, str) or len(registration_challenge_digest) != 64:
        raise PermissionError("registration challenge identity required")
    if first:
        # Even a direct internal call cannot silently bootstrap another owner.
        # Test fixtures bypass this only by patching the platform guard.
        from sofia.safe.owner_enroll_browser import require_venus_interactive_windows
        require_venus_interactive_windows()
    moment = _utc(at or datetime.now(timezone.utc))
    with closing(verifier._db()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        known = db.execute("SELECT COUNT(*) FROM safe_owner_credential").fetchone()[0]
        if first:
            if known:
                raise PermissionError("first enrollment cannot be reopened after any credential")
            if authorizing_event_id is not None:
                raise PermissionError("first enrollment uses attended Windows trust bootstrap")
        else:
            if not known or not isinstance(authorizing_event_id, str):
                raise PermissionError("additional enrollment requires existing owner authenticator")
            row = db.execute(
                "SELECT ch.action_fingerprint,ch.consumed_at FROM safe_owner_challenge ch "
                "JOIN safe_audit_event ev ON ev.event_id=? "
                "WHERE ch.challenge_digest=? AND ev.event_type='owner.webauthn.verified'",
                (authorizing_event_id, authorizing_event_id.removeprefix("owner-webauthn:")),
            ).fetchone()
            if row is None or row["consumed_at"] is None or row["action_fingerprint"] != sha256(
                ("owner.enroll:" + kind + ":" + registration_challenge_digest).encode("ascii")
            ).hexdigest():
                raise PermissionError("existing owner proof not bound to new credential ceremony")
            db.execute("""
                CREATE TABLE IF NOT EXISTS safe_owner_enrollment_authorization (
                    authentication_event_id TEXT PRIMARY KEY,
                    credential_id TEXT NOT NULL UNIQUE
                )
            """)
            if db.execute(
                "SELECT 1 FROM safe_owner_enrollment_authorization "
                "WHERE authentication_event_id=?", (authorizing_event_id,),
            ).fetchone():
                raise PermissionError("enrollment proof already spent")
        db.execute(
            "INSERT INTO safe_owner_credential "
            "(credential_id,public_key_der,credential_kind,sign_count,enrolled_at) "
            "VALUES(?,?,?,?,?)",
            (credential_id, public_key_der, kind, count, moment.isoformat()),
        )
        if not first:
            db.execute(
                "INSERT INTO safe_owner_enrollment_authorization "
                "(authentication_event_id,credential_id) VALUES(?,?)",
                (authorizing_event_id, credential_id),
            )
        verifier.audit.append_in_transaction(
            db, actor_id="Sparks", event_type="owner.credential.enrolled",
            payload={
                "credential_id_sha256": sha256(credential_id.encode()).hexdigest(),
                "kind": kind, "first": first,
                "registration_challenge_digest": registration_challenge_digest,
                "authorizing_event_id": authorizing_event_id,
                "attestation": "none; credential hardware provenance unverified",
            },
            occurred_at=moment,
        )


def revoke_enrollment(
    verifier: OwnerWebAuthnVerifier, *, credential_id: str,
    approval_id: str, now: datetime | None = None,
) -> None:
    """Revoke a reviewed key after a separate live FIDO2 exact-action receipt.

    Retain at least one active security key, to prevent lockout or downgrading
    the high-assurance action gate to a platform credential. Preserve revoked
    registrations in canonical history to prevent first-enrollment reset.
    """
    from sofia.safe.execution_approval import ExecutionApprovalVerifier
    if not isinstance(verifier, OwnerWebAuthnVerifier):
        raise TypeError("canonical credential verifier required")
    _unb64(credential_id, limit=1024)
    moment = _utc(now or datetime.now(timezone.utc))
    with closing(verifier._db()) as db:
        row = db.execute(
            "SELECT credential_kind,revoked_at FROM safe_owner_credential "
            "WHERE credential_id=?", (credential_id,),
        ).fetchone()
        if row is None or row["revoked_at"] is not None:
            raise PermissionError("credential is absent or already revoked")
        if row["credential_kind"] == "security_key":
            count = db.execute(
                "SELECT COUNT(*) FROM safe_owner_credential "
                "WHERE credential_kind='security_key' AND revoked_at IS NULL",
            ).fetchone()[0]
            if count <= 1:
                raise PermissionError(
                    "refusing to revoke the last active security key without offline recovery"
                )
    parameters = {"credential_id": credential_id}
    ExecutionApprovalVerifier(verifier._guard.path).consume(
        approval_id=approval_id, capability="owner.credentials.revoke",
        parameters=parameters, now=moment,
    )
    with closing(verifier._db()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT credential_kind,revoked_at FROM safe_owner_credential "
            "WHERE credential_id=?", (credential_id,),
        ).fetchone()
        if row is None or row["revoked_at"] is not None:
            raise PermissionError("credential already revoked during authorization")
        if row["credential_kind"] == "security_key":
            count = db.execute(
                "SELECT COUNT(*) FROM safe_owner_credential "
                "WHERE credential_kind='security_key' AND revoked_at IS NULL",
            ).fetchone()[0]
            if count <= 1:
                raise PermissionError("last active security key cannot be revoked")
        changed = db.execute(
            "UPDATE safe_owner_credential SET revoked_at=? "
            "WHERE credential_id=? AND revoked_at IS NULL",
            (moment.isoformat(), credential_id),
        )
        if changed.rowcount != 1:
            raise PermissionError("credential revocation conflicted")
        verifier.audit.append_in_transaction(
            db, actor_id="Sparks", event_type="owner.credential.revoked",
            payload={
                "credential_id_sha256": sha256(credential_id.encode()).hexdigest(),
                "approval_id": approval_id,
            }, occurred_at=moment,
        )
