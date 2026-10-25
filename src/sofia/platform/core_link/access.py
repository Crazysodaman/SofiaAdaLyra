"""Canonical host-side authorization for enrolled Core Link clients.

The local binding registry identifies where a client intends to connect.  This
store is the independent Core-host half of that relationship: it binds one
mutually authenticated client certificate to one Platform, principal,
audience, Core identity/generation and bounded scope set.  Enrollment and
revocation consume exact one-use SAFE approvals in the same canonical SQLite
transaction as the access change.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.sdk.contracts import ProtocolVersion


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_SCOPE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
_ENROLL_CAPABILITY = "core-link.enroll"
_REVOKE_CAPABILITY = "core-link.revoke"


def _utc(value: datetime, label: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


@dataclass(frozen=True, slots=True)
class CoreLinkClientAccess:
    client_id: str
    certificate_public_key_sha256: str
    local_platform_id: str
    remote_platform_id: str
    remote_core_identity_id: str
    remote_core_generation: int
    principal: PrincipalContext
    scopes: tuple[str, ...]
    protocol_version: ProtocolVersion
    enrolled_at: datetime
    expires_at: datetime
    revision: int = 1
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for label in (
            "client_id", "local_platform_id", "remote_platform_id",
            "remote_core_identity_id",
        ):
            _id(getattr(self, label), label)
        if _FINGERPRINT.fullmatch(self.certificate_public_key_sha256) is None:
            raise ValueError("client certificate fingerprint must be lowercase SHA-256")
        if type(self.remote_core_generation) is not int or self.remote_core_generation < 1:
            raise ValueError("remote_core_generation must be positive")
        if not isinstance(self.principal, PrincipalContext):
            raise TypeError("principal must be authenticated PrincipalContext")
        if (
            not isinstance(self.scopes, tuple)
            or not self.scopes
            or len(self.scopes) > 32
            or len(set(self.scopes)) != len(self.scopes)
            or any(_SCOPE.fullmatch(scope) is None for scope in self.scopes)
        ):
            raise ValueError("scopes must be a bounded unique scope tuple")
        if not isinstance(self.protocol_version, ProtocolVersion):
            raise TypeError("protocol_version must be ProtocolVersion")
        enrolled = _utc(self.enrolled_at, "enrolled_at")
        expires = _utc(self.expires_at, "expires_at")
        if expires <= enrolled:
            raise ValueError("client access expiry must follow enrollment")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("client access revision must be positive")
        if self.revoked_at is not None and _utc(
            self.revoked_at, "revoked_at"
        ) < enrolled:
            raise ValueError("revocation cannot precede enrollment")

    def parameters(self) -> dict[str, object]:
        """Exact SAFE approval parameters; never includes mutable labels."""
        return {
            "client_id": self.client_id,
            "certificate_public_key_sha256": self.certificate_public_key_sha256,
            "local_platform_id": self.local_platform_id,
            "remote_platform_id": self.remote_platform_id,
            "remote_core_identity_id": self.remote_core_identity_id,
            "remote_core_generation": self.remote_core_generation,
            "principal_id": self.principal.principal_id,
            "audience_id": self.principal.audience_id,
            "audience_kind": self.principal.audience_kind.value,
            "scopes": list(self.scopes),
            "protocol_version": str(self.protocol_version),
            "expires_at": _utc(self.expires_at, "expires_at").isoformat(),
        }

    def require_scope(self, scope: str, *, now: datetime) -> None:
        moment = _utc(now, "now")
        if self.revoked_at is not None:
            raise PermissionError("Core Link client access is revoked")
        if moment >= _utc(self.expires_at, "expires_at"):
            raise PermissionError("Core Link client access expired")
        if scope not in self.scopes:
            raise PermissionError("Core Link client lacks required scope")


class CoreLinkClientAccessStore:
    """Canonical access projection; not a client binding or secret store."""

    def __init__(
        self, state_path: Path | str, *,
        approvals: ExecutionApprovalVerifier | None = None,
    ) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        self.approvals = approvals or ExecutionApprovalVerifier(self.path)
        self.stop = OperatorStopStore(self.path)
        with closing(self._connect()) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS core_link_client_access(
                client_id TEXT PRIMARY KEY,
                certificate_public_key_sha256 TEXT NOT NULL UNIQUE,
                local_platform_id TEXT NOT NULL,
                remote_platform_id TEXT NOT NULL,
                remote_core_identity_id TEXT NOT NULL,
                remote_core_generation INTEGER NOT NULL,
                principal_id TEXT NOT NULL,
                audience_id TEXT NOT NULL,
                audience_kind TEXT NOT NULL,
                scopes TEXT NOT NULL,
                protocol_version TEXT NOT NULL,
                enrolled_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revision INTEGER NOT NULL,
                revoked_at TEXT
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _decode(row: sqlite3.Row) -> CoreLinkClientAccess:
        scopes = tuple(value for value in row["scopes"].split("\n") if value)
        return CoreLinkClientAccess(
            client_id=row["client_id"],
            certificate_public_key_sha256=row["certificate_public_key_sha256"],
            local_platform_id=row["local_platform_id"],
            remote_platform_id=row["remote_platform_id"],
            remote_core_identity_id=row["remote_core_identity_id"],
            remote_core_generation=int(row["remote_core_generation"]),
            principal=PrincipalContext(
                row["principal_id"], row["audience_id"],
                AudienceKind(row["audience_kind"]),
            ),
            scopes=scopes,
            protocol_version=ProtocolVersion.parse(row["protocol_version"]),
            enrolled_at=datetime.fromisoformat(row["enrolled_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            revision=int(row["revision"]),
            revoked_at=(
                None if row["revoked_at"] is None
                else datetime.fromisoformat(row["revoked_at"])
            ),
        )

    def enroll(
        self, access: CoreLinkClientAccess, *, approval_id: str,
        now: datetime,
    ) -> CoreLinkClientAccess:
        if not isinstance(access, CoreLinkClientAccess):
            raise TypeError("access must be CoreLinkClientAccess")
        moment = _utc(now, "now")
        if self.stop.current().active:
            raise PermissionError("operator stop blocks Core Link enrollment")
        if access.revision != 1 or access.revoked_at is not None:
            raise ValueError("new Core Link access must be active revision 1")
        if moment < _utc(access.enrolled_at, "enrolled_at"):
            raise PermissionError("Core Link enrollment is not active yet")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self.approvals.consume(
                approval_id=approval_id, capability=_ENROLL_CAPABILITY,
                parameters=access.parameters(), now=moment,
                _transaction_db=db,
            )
            db.execute(
                """INSERT INTO core_link_client_access(
                client_id,certificate_public_key_sha256,local_platform_id,
                remote_platform_id,remote_core_identity_id,
                remote_core_generation,principal_id,audience_id,audience_kind,
                scopes,protocol_version,enrolled_at,expires_at,revision,revoked_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    access.client_id, access.certificate_public_key_sha256,
                    access.local_platform_id, access.remote_platform_id,
                    access.remote_core_identity_id, access.remote_core_generation,
                    access.principal.principal_id, access.principal.audience_id,
                    access.principal.audience_kind.value, "\n".join(access.scopes),
                    str(access.protocol_version),
                    _utc(access.enrolled_at, "enrolled_at").isoformat(),
                    _utc(access.expires_at, "expires_at").isoformat(), 1,
                ),
            )
            db.commit()
        return access

    def authenticate(
        self, certificate_public_key_sha256: str, *, now: datetime,
    ) -> CoreLinkClientAccess | None:
        if _FINGERPRINT.fullmatch(certificate_public_key_sha256) is None:
            return None
        moment = _utc(now, "now")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM core_link_client_access "
                "WHERE certificate_public_key_sha256=?",
                (certificate_public_key_sha256,),
            ).fetchone()
        if row is None:
            return None
        try:
            access = self._decode(row)
        except (TypeError, ValueError):
            return None
        if access.revoked_at is not None or moment >= access.expires_at.astimezone(
            timezone.utc
        ):
            return None
        return access

    def revoke(
        self, client_id: str, *, expected_revision: int,
        approval_id: str, now: datetime,
    ) -> CoreLinkClientAccess:
        _id(client_id, "client_id")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        moment = _utc(now, "now")
        if self.stop.current().active:
            raise PermissionError("operator stop blocks Core Link revocation")
        parameters = {
            "client_id": client_id,
            "expected_revision": expected_revision,
        }
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM core_link_client_access WHERE client_id=?",
                (client_id,),
            ).fetchone()
            if row is None:
                raise KeyError(client_id)
            current = self._decode(row)
            if current.revision != expected_revision:
                raise RuntimeError("Core Link access revision conflict")
            if current.revoked_at is not None:
                raise PermissionError("Core Link access is already revoked")
            self.approvals.consume(
                approval_id=approval_id, capability=_REVOKE_CAPABILITY,
                parameters=parameters, now=moment, _transaction_db=db,
            )
            changed = db.execute(
                "UPDATE core_link_client_access SET revoked_at=?,revision=revision+1 "
                "WHERE client_id=? AND revision=? AND revoked_at IS NULL",
                (moment.isoformat(), client_id, expected_revision),
            )
            if changed.rowcount != 1:
                raise RuntimeError("Core Link access changed concurrently")
            row = db.execute(
                "SELECT * FROM core_link_client_access WHERE client_id=?",
                (client_id,),
            ).fetchone()
            db.commit()
        return self._decode(row)
