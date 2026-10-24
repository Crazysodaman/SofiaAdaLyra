"""Scoped secret-reference broker over the existing protected secret store."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3
from typing import Callable, Protocol

from sofia.platform.safe.secret_store import ProtectedSecretStore
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_REF = re.compile(r"^secret:[a-z][a-z0-9_.-]{1,126}$")
_MODULE = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$")


class SecretValueStore(Protocol):
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...
    def clear(self, key: str) -> bool: ...


SecretAuthorizer = Callable[
    [PrincipalContext, str, str, str, str, datetime], bool
]


@dataclass(frozen=True, slots=True)
class SecretMetadata:
    secret_ref: str
    owner_module: str
    audience_id: str
    allowed_modules: tuple[str, ...]
    version: int
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None

    def __repr__(self) -> str:
        return (
            f"SecretMetadata(secret_ref={self.secret_ref!r}, "
            f"owner_module={self.owner_module!r}, audience_id='[REDACTED]', "
            f"allowed_modules={self.allowed_modules!r}, version={self.version}, "
            f"revoked={self.revoked_at is not None})"
        )


@dataclass(frozen=True, slots=True)
class SecretRotationPlan:
    secret_ref: str
    current_version: int
    next_version: int
    impacted_modules: tuple[str, ...]
    required_authority: str = "secret.rotate"
    executable: bool = False


class SecretLease:
    """One-use, short-lived plaintext handoff with redacted representation."""

    __slots__ = ("secret_ref", "version", "expires_at", "_value", "_taken")

    def __init__(self, secret_ref: str, version: int, expires_at: datetime,
                 value: str) -> None:
        self.secret_ref = secret_ref
        self.version = version
        self.expires_at = expires_at
        self._value = value
        self._taken = False

    def __repr__(self) -> str:
        return (
            f"SecretLease(secret_ref={self.secret_ref!r}, version={self.version}, "
            "value='[REDACTED]')"
        )

    def take(self, *, now: datetime) -> str:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if self._taken:
            raise PermissionError("secret lease was already consumed")
        if now.astimezone(timezone.utc) >= self.expires_at:
            self._value = ""
            self._taken = True
            raise PermissionError("secret lease expired")
        value = self._value
        self._value = ""
        self._taken = True
        return value


class PlatformSecretsBroker:
    """Keep values in ProtectedSecretStore and metadata in canonical state."""

    def __init__(self, state_path: Path, *, authorizer: SecretAuthorizer,
                 value_store: SecretValueStore | None = None) -> None:
        if not isinstance(state_path, Path) or not callable(authorizer):
            raise TypeError("state_path and authorizer are required")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.authorizer = authorizer
        self.value_store = value_store or ProtectedSecretStore.for_state_path(state_path)
        with closing(self._connect()) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS platform_secret_reference(
                secret_ref TEXT PRIMARY KEY,owner_module TEXT NOT NULL,
                audience_id TEXT NOT NULL,allowed_modules_json TEXT NOT NULL,
                version INTEGER NOT NULL CHECK(version>0),
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL,revoked_at TEXT)"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("time must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _validate_ref(value: str) -> None:
        if not isinstance(value, str) or _REF.fullmatch(value) is None:
            raise ValueError("invalid secret reference")

    @staticmethod
    def _validate_modules(values: tuple[str, ...]) -> tuple[str, ...]:
        if type(values) is not tuple or not values or any(
            not isinstance(item, str) or _MODULE.fullmatch(item) is None
            for item in values
        ) or len(set(values)) != len(values):
            raise ValueError("allowed_modules must be unique module identities")
        return tuple(sorted(values))

    @staticmethod
    def _key(secret_ref: str, version: int) -> str:
        return "platform-" + sha256(f"{secret_ref}\0{version}".encode()).hexdigest()

    @staticmethod
    def _metadata(row: sqlite3.Row) -> SecretMetadata:
        return SecretMetadata(
            row["secret_ref"], row["owner_module"], row["audience_id"],
            tuple(json.loads(row["allowed_modules_json"])), int(row["version"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
            None if row["revoked_at"] is None else datetime.fromisoformat(row["revoked_at"]),
        )

    def inspect(self, secret_ref: str) -> SecretMetadata | None:
        self._validate_ref(secret_ref)
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_secret_reference WHERE secret_ref=?",
                (secret_ref,),
            ).fetchone()
        return None if row is None else self._metadata(row)

    def create(self, *, secret_ref: str, value: str, owner_module: str,
               audience_id: str, allowed_modules: tuple[str, ...],
               principal: PrincipalContext, authority_ref: str,
               now: datetime) -> SecretMetadata:
        self._validate_ref(secret_ref)
        allowed = self._validate_modules(allowed_modules)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if _MODULE.fullmatch(owner_module) is None or owner_module not in allowed:
            raise ValueError("owner_module must be an allowed module identity")
        if not isinstance(audience_id, str) or not audience_id.strip():
            raise ValueError("audience_id required")
        if not isinstance(value, str) or not value:
            raise ValueError("secret value must be nonempty")
        moment = self._utc(now)
        if principal.audience_kind is not AudienceKind.PRIVATE or (
            principal.audience_id != audience_id
        ):
            raise PermissionError("secret creation audience mismatch")
        if not self.authorizer(
            principal, owner_module, secret_ref, "create", authority_ref, moment,
        ):
            raise PermissionError("secret creation is not authorized")
        key = self._key(secret_ref, 1)
        self.value_store.set(key, value)
        try:
            with closing(self._connect()) as db, db:
                db.execute(
                    """INSERT INTO platform_secret_reference VALUES(?,?,?,?,1,?,?,NULL)""",
                    (secret_ref, owner_module, audience_id,
                     json.dumps(allowed, separators=(",", ":")),
                     moment.isoformat(), moment.isoformat()),
                )
        except BaseException:
            self.value_store.clear(key)
            raise
        return self.inspect(secret_ref)  # type: ignore[return-value]

    def disclose(self, *, secret_ref: str, caller_module: str,
                 principal: PrincipalContext, authority_ref: str, purpose: str,
                 now: datetime, ttl: timedelta = timedelta(seconds=30)) -> SecretLease:
        moment = self._utc(now)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if not isinstance(caller_module, str) or _MODULE.fullmatch(caller_module) is None:
            raise ValueError("invalid caller_module")
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("secret disclosure purpose required")
        if not isinstance(ttl, timedelta) or not timedelta(seconds=1) <= ttl <= timedelta(minutes=5):
            raise ValueError("secret lease TTL must be in 1 second..5 minutes")
        metadata = self.inspect(secret_ref)
        if metadata is None or metadata.revoked_at is not None:
            raise PermissionError("secret reference is unavailable or revoked")
        if (principal.audience_kind is not AudienceKind.PRIVATE
                or principal.audience_id != metadata.audience_id):
            raise PermissionError("secret audience mismatch")
        if caller_module not in metadata.allowed_modules:
            raise PermissionError("module is outside secret allowlist")
        if not self.authorizer(
            principal, caller_module, secret_ref, purpose, authority_ref, moment,
        ):
            raise PermissionError("secret disclosure is not authorized")
        value = self.value_store.get(self._key(secret_ref, metadata.version))
        if value is None:
            raise RuntimeError("protected secret material is unavailable")
        return SecretLease(secret_ref, metadata.version, moment + ttl, value)

    def plan_rotation(self, secret_ref: str) -> SecretRotationPlan:
        metadata = self.inspect(secret_ref)
        if metadata is None or metadata.revoked_at is not None:
            raise LookupError("active secret reference required")
        return SecretRotationPlan(
            secret_ref, metadata.version, metadata.version + 1,
            metadata.allowed_modules,
        )

    def rotate(self, *, secret_ref: str, value: str, expected_version: int,
               principal: PrincipalContext, authority_ref: str,
               now: datetime) -> SecretMetadata:
        moment = self._utc(now)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("expected_version must be positive")
        metadata = self.inspect(secret_ref)
        if metadata is None or metadata.revoked_at is not None:
            raise LookupError("active secret reference required")
        if principal.audience_kind is not AudienceKind.PRIVATE or (
            principal.audience_id != metadata.audience_id
        ):
            raise PermissionError("secret rotation audience mismatch")
        if not self.authorizer(
            principal, metadata.owner_module, secret_ref, "rotate",
            authority_ref, moment,
        ):
            raise PermissionError("secret rotation is not authorized")
        if not isinstance(value, str) or not value:
            raise ValueError("secret value must be nonempty")
        next_version = expected_version + 1
        key = self._key(secret_ref, next_version)
        self.value_store.set(key, value)
        try:
            with closing(self._connect()) as db, db:
                changed = db.execute(
                    """UPDATE platform_secret_reference SET version=?,updated_at=?
                    WHERE secret_ref=? AND version=? AND revoked_at IS NULL""",
                    (next_version, moment.isoformat(), secret_ref, expected_version),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("secret revision changed before rotation")
        except BaseException:
            self.value_store.clear(key)
            raise
        return self.inspect(secret_ref)  # type: ignore[return-value]

    def revoke(self, *, secret_ref: str, principal: PrincipalContext,
               authority_ref: str, now: datetime) -> SecretMetadata:
        moment = self._utc(now)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        metadata = self.inspect(secret_ref)
        if metadata is None:
            raise LookupError("unknown secret reference")
        if principal.audience_kind is not AudienceKind.PRIVATE or (
            principal.audience_id != metadata.audience_id
        ):
            raise PermissionError("secret revocation audience mismatch")
        if not self.authorizer(
            principal, metadata.owner_module, secret_ref, "revoke",
            authority_ref, moment,
        ):
            raise PermissionError("secret revocation is not authorized")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE platform_secret_reference SET revoked_at=?,updated_at=?
                WHERE secret_ref=? AND revoked_at IS NULL""",
                (moment.isoformat(), moment.isoformat(), secret_ref),
            )
            if changed.rowcount != 1:
                raise PermissionError("secret is already revoked")
        # Metadata revocation is authoritative and commits first. Failure to
        # erase an encrypted historical blob cannot revive disclosure.
        for version in range(1, metadata.version + 1):
            self.value_store.clear(self._key(secret_ref, version))
        return self.inspect(secret_ref)  # type: ignore[return-value]
