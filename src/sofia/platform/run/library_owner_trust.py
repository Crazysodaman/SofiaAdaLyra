"""D028 personal-use, single-owner Library publisher trust.

ONE current owner-selected Hub publisher per installed Platform, stored in the
EXISTING identity-pinned local SQLite database. No tenant registry, commercial
certificate authority, third-party cloud, extra daemon or automatic TOFU.

Enrollment/rotation and revocation consume distinct exact, one-use owner SAFE
approvals IN THE SAME SQLite transaction as the trust row and hash-chain audit.
Revocation is allowed during STOP; reading/serving is not. A revoked identity
cannot be resurrected by replacing the signed index file. Key rotation
requires revocation, a strictly newer catalog generation and nondecreasing
rollback floor, with its own separately authenticated enrollment.

The public key in the owner-private signed-index profile is never the trust
anchor. The record here is the independent owner-enrolled pin.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Callable

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.run.library_installed_catalog import InstalledLibraryCatalogProvider
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.ops.library_signed_index import verify_signed_library_index
from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.local_store import PlatformLocalStore

ENROLL_CAPABILITY = "platform.library.owner_trust.enroll"
REVOKE_CAPABILITY = "platform.library.owner_trust.revoke"
_TRUST_TABLE = "platform_library_owner_publisher"
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_MAX = 2**53 - 1


class OwnerLibraryTrustDenied(PermissionError):
    """No authenticated current owner root for this installed Platform."""


@dataclass(frozen=True, slots=True)
class OwnerLibraryPublisher:
    platform_id: str
    source_platform_id: str
    public_key: bytes
    public_key_sha256: str
    catalog_generation: int
    minimum_catalog_revision: int
    trust_generation: int
    revoked_at: datetime | None

    def __post_init__(self) -> None:
        if (type(self.platform_id) is not str
                or _ID.fullmatch(self.platform_id) is None
                or type(self.source_platform_id) is not str
                or _ID.fullmatch(self.source_platform_id) is None
                or self.source_platform_id == self.platform_id
                or type(self.public_key) is not bytes
                or len(self.public_key) != 32
                or type(self.public_key_sha256) is not str
                or _HEX.fullmatch(self.public_key_sha256) is None
                or sha256(self.public_key).hexdigest() != self.public_key_sha256):
            raise OwnerLibraryTrustDenied("owner publisher key or source binding corrupt")
        for n in ("catalog_generation", "minimum_catalog_revision", "trust_generation"):
            value = getattr(self, n)
            if type(value) is not int or not 1 <= value <= _MAX:
                raise OwnerLibraryTrustDenied("owner trust epoch or rollback floor invalid")
        if self.revoked_at is not None and (
            not isinstance(self.revoked_at, datetime)
            or self.revoked_at.utcoffset() is None
        ):
            raise OwnerLibraryTrustDenied("owner revocation timestamp invalid")

    @property
    def active(self) -> bool:
        return self.revoked_at is None


def enrollment_parameters(
    *, state_path: Path | str, platform_id: str, source_platform_id: str,
    public_key: bytes, catalog_generation: int,
    minimum_catalog_revision: int, previous_trust_generation: int,
) -> dict[str, object]:
    """Exact scope for a separately verified one-use owner action."""
    for name, value in (
        ("platform_id", platform_id), ("source_platform_id", source_platform_id),
    ):
        if type(value) is not str or _ID.fullmatch(value) is None:
            raise OwnerLibraryTrustDenied(f"exact {name} required")
    if platform_id == source_platform_id:
        raise OwnerLibraryTrustDenied("a Hub source is a distinct enrolled Platform")
    if type(public_key) is not bytes or len(public_key) != 32:
        raise OwnerLibraryTrustDenied("32-byte owner-selected Ed25519 public key required")
    for number, minimum in (
        (catalog_generation, 1), (minimum_catalog_revision, 1),
        (previous_trust_generation, 0),
    ):
        if type(number) is not int or not minimum <= number <= _MAX:
            raise OwnerLibraryTrustDenied("bounded epoch and previous owner trust pin required")
    return {
        "schema": "aegis.platform.library.owner-trust-enroll.v1",
        "state_path": str(Path(state_path).absolute()),
        "platform_id": platform_id,
        "source_platform_id": source_platform_id,
        "publisher_public_key_sha256": sha256(public_key).hexdigest(),
        "catalog_generation": catalog_generation,
        "minimum_catalog_revision": minimum_catalog_revision,
        "previous_trust_generation": previous_trust_generation,
    }


def revocation_parameters(*, state_path: Path | str, pin: OwnerLibraryPublisher) -> dict[str, object]:
    if not isinstance(pin, OwnerLibraryPublisher):
        raise OwnerLibraryTrustDenied("current owner trust pin required for revocation")
    return {
        "schema": "aegis.platform.library.owner-trust-revoke.v1",
        "state_path": str(Path(state_path).absolute()),
        "platform_id": pin.platform_id,
        "source_platform_id": pin.source_platform_id,
        "publisher_public_key_sha256": pin.public_key_sha256,
        "catalog_generation": pin.catalog_generation,
        "trust_generation": pin.trust_generation,
    }


class OwnerLibraryTrustStore:
    """Personal Aegis publisher root using the existing owner + local SQLite."""

    def __init__(
        self, state_path: Path | str, *,
        platform_id: str, catalog_profile: Path | str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if type(platform_id) is not str or _ID.fullmatch(platform_id) is None:
            raise OwnerLibraryTrustDenied("installed immutable Platform identity required")
        self.path = Path(state_path).absolute()
        self.platform_id = platform_id
        self.profile = (
            Path(catalog_profile).absolute()
            if catalog_profile is not None
            else self.path.parent / "library-catalog.json"
        )
        if clock is not None and not callable(clock):
            raise TypeError("owner trust service clock required")
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.state = PlatformLocalStore(
            self.path, create=False, host_identity=platform_id,
            roles=PlatformRoleConfiguration((PlatformRole.MODULE_HOST,)),
        )
        self.audit = AuditChain(self.path)
        self.approvals = ExecutionApprovalVerifier(self.path)
        self.stop = OperatorStopStore(self.path)

    def _now(self) -> datetime:
        at = self.clock()
        if not isinstance(at, datetime) or at.utcoffset() is None:
            raise OwnerLibraryTrustDenied("current owner trust clock required")
        return at.astimezone(timezone.utc)

    def _connect(self) -> sqlite3.Connection:
        self.state.validate()
        db = self.state.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.execute("""
            CREATE TABLE IF NOT EXISTS platform_library_owner_publisher (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                platform_id TEXT NOT NULL,
                source_platform_id TEXT NOT NULL,
                public_key BLOB NOT NULL,
                public_key_sha256 TEXT NOT NULL,
                catalog_generation INTEGER NOT NULL CHECK(catalog_generation>0),
                minimum_catalog_revision INTEGER NOT NULL CHECK(minimum_catalog_revision>0),
                trust_generation INTEGER NOT NULL CHECK(trust_generation>0),
                enrolled_at TEXT NOT NULL,
                revoked_at TEXT
            )
        """)

    @staticmethod
    def _create_index_schema(db: sqlite3.Connection) -> None:
        db.execute("""
            CREATE TABLE IF NOT EXISTS platform_library_owner_index (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                trust_generation INTEGER NOT NULL CHECK(trust_generation>0),
                catalog_revision INTEGER NOT NULL CHECK(catalog_revision>0),
                issued_at TEXT NOT NULL,
                signed_index_sha256 TEXT NOT NULL,
                signed_index BLOB NOT NULL CHECK(length(signed_index)<=65536)
            )
        """)

    @staticmethod
    def _index(db: sqlite3.Connection):
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("platform_library_owner_index",),
        ).fetchone()
        if exists is None:
            return None
        return db.execute(
            "SELECT trust_generation,catalog_revision,issued_at,"
            "signed_index_sha256,signed_index FROM platform_library_owner_index "
            "WHERE singleton=1"
        ).fetchone()

    @staticmethod
    def _read(db: sqlite3.Connection) -> OwnerLibraryPublisher | None:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (_TRUST_TABLE,),
        ).fetchone()
        if exists is None:
            return None
        row = db.execute(
            "SELECT platform_id,source_platform_id,public_key,public_key_sha256,"
            "catalog_generation,minimum_catalog_revision,trust_generation,revoked_at "
            "FROM platform_library_owner_publisher WHERE singleton=1"
        ).fetchone()
        if row is None:
            return None
        try:
            return OwnerLibraryPublisher(
                platform_id=row["platform_id"], source_platform_id=row["source_platform_id"],
                public_key=bytes(row["public_key"]),
                public_key_sha256=row["public_key_sha256"],
                catalog_generation=row["catalog_generation"],
                minimum_catalog_revision=row["minimum_catalog_revision"],
                trust_generation=row["trust_generation"],
                revoked_at=(
                    None if row["revoked_at"] is None
                    else datetime.fromisoformat(row["revoked_at"])
                ),
            )
        except (TypeError, ValueError, KeyError) as exc:
            raise OwnerLibraryTrustDenied("corrupt owner Library trust record") from exc

    def current(self) -> OwnerLibraryPublisher | None:
        """Read-only, no auto-enrollment. Missing trust is a normal fresh install."""
        with closing(self._connect()) as db:
            pin = self._read(db)
        if pin is None:
            return None
        if pin.platform_id != self.platform_id:
            raise OwnerLibraryTrustDenied("owner trust belongs to another installed Platform")
        return pin

    def publisher_current(self, public_key_sha256: str, trust_generation: int) -> bool:
        if (type(public_key_sha256) is not str
                or _HEX.fullmatch(public_key_sha256) is None
                or type(trust_generation) is not int):
            return False
        try:
            current = self.current()
            return (
                current is not None and current.active
                and current.public_key_sha256 == public_key_sha256
                and current.trust_generation == trust_generation
                and not self.stop.current().active
            )
        except (OSError, sqlite3.Error, ValueError, PermissionError, RuntimeError):
            return False

    def enroll(
        self, *, source_platform_id: str, public_key: bytes,
        catalog_generation: int, minimum_catalog_revision: int,
        approval_id: str,
    ) -> OwnerLibraryPublisher:
        """One owner-approved pin; no trust-on-first-use or silent key rotation."""
        now = self._now()
        if self.stop.current().active:
            raise OwnerLibraryTrustDenied("STOP prevents owner trust enrollment")
        if type(approval_id) is not str or not approval_id.strip():
            raise OwnerLibraryTrustDenied("authenticated one-use owner approval required")
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                previous = self._read(db)
                if previous is not None:
                    if previous.platform_id != self.platform_id:
                        raise OwnerLibraryTrustDenied("foreign Platform trust record")
                    if previous.active:
                        raise OwnerLibraryTrustDenied("revoke current publisher before owner rotation")
                    if (catalog_generation <= previous.catalog_generation
                            or minimum_catalog_revision < previous.minimum_catalog_revision):
                        raise OwnerLibraryTrustDenied("owner rotation must advance catalog epoch and floor")
                prior_version = previous.trust_generation if previous is not None else 0
                parameters = enrollment_parameters(
                    state_path=self.path, platform_id=self.platform_id,
                    source_platform_id=source_platform_id, public_key=public_key,
                    catalog_generation=catalog_generation,
                    minimum_catalog_revision=minimum_catalog_revision,
                    previous_trust_generation=prior_version,
                )
                approval = self.approvals.consume(
                    approval_id=approval_id, capability=ENROLL_CAPABILITY,
                    parameters=parameters, now=now, _transaction_db=db,
                )
                self._create_schema(db)
                self._create_index_schema(db)
                db.execute("DELETE FROM platform_library_owner_index WHERE singleton=1")
                key_digest = sha256(public_key).hexdigest()
                db.execute("""
                    INSERT INTO platform_library_owner_publisher (
                        singleton,platform_id,source_platform_id,public_key,
                        public_key_sha256,catalog_generation,minimum_catalog_revision,
                        trust_generation,enrolled_at,revoked_at
                    ) VALUES (1,?,?,?,?,?,?,?,?,NULL)
                    ON CONFLICT(singleton) DO UPDATE SET
                        platform_id=excluded.platform_id,
                        source_platform_id=excluded.source_platform_id,
                        public_key=excluded.public_key,
                        public_key_sha256=excluded.public_key_sha256,
                        catalog_generation=excluded.catalog_generation,
                        minimum_catalog_revision=excluded.minimum_catalog_revision,
                        trust_generation=excluded.trust_generation,
                        enrolled_at=excluded.enrolled_at,
                        revoked_at=NULL
                """, (
                    self.platform_id, source_platform_id, public_key, key_digest,
                    catalog_generation, minimum_catalog_revision,
                    prior_version + 1, now.isoformat(),
                ))
                self.audit.append_in_transaction(
                    db, actor_id=approval.approved_by,
                    event_type="library.owner.publisher.enrolled",
                    event_id="library-owner-publisher-enroll:" + approval_id,
                    occurred_at=now, payload={
                        **parameters, "trust_generation": prior_version + 1,
                        "approval_id": approval_id,
                    },
                )
                db.commit()
        pin = self.current()
        if pin is None or not pin.active:
            raise RuntimeError("owner publisher commit needs reconciliation")
        return pin

    def revoke(self, *, approval_id: str) -> OwnerLibraryPublisher:
        """Explicit owner revocation, even during STOP, transactionally audited."""
        now = self._now()
        if type(approval_id) is not str or not approval_id.strip():
            raise OwnerLibraryTrustDenied("authenticated owner revocation required")
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                pin = self._read(db)
                if pin is None or pin.platform_id != self.platform_id or not pin.active:
                    raise OwnerLibraryTrustDenied("no active owner publisher to revoke")
                params = revocation_parameters(state_path=self.path, pin=pin)
                approval = self.approvals.consume(
                    approval_id=approval_id, capability=REVOKE_CAPABILITY,
                    parameters=params, now=now, _transaction_db=db,
                )
                changed = db.execute(
                    "UPDATE platform_library_owner_publisher SET revoked_at=? "
                    "WHERE singleton=1 AND trust_generation=? AND revoked_at IS NULL",
                    (now.isoformat(), pin.trust_generation),
                )
                if changed.rowcount != 1:
                    raise OwnerLibraryTrustDenied("publisher changed during owner revocation")
                self._create_index_schema(db)
                db.execute("DELETE FROM platform_library_owner_index WHERE singleton=1")
                self.audit.append_in_transaction(
                    db, actor_id=approval.approved_by,
                    event_type="library.owner.publisher.revoked",
                    event_id="library-owner-publisher-revoke:" + approval_id,
                    occurred_at=now, payload={**params, "approval_id": approval_id},
                )
                db.commit()
        result = self.current()
        if result is None or result.active:
            raise RuntimeError("owner publisher revocation needs reconciliation")
        return result

    def __call__(self):
        """Read current installed signed catalog, or None on fresh installs.

        The owner-private profile is merely a snapshot signed by the pinned
        Hub publisher. It cannot self-enroll the embedded public key.
        """
        pin = self.current()
        if pin is None or not pin.active or self.stop.current().active:
            return None
        if not self.profile.is_file():
            return None
        provider = InstalledLibraryCatalogProvider(
            profile=self.profile,
            expected_publisher_key_sha256=pin.public_key_sha256,
            expected_source_platform_id=pin.source_platform_id,
            expected_target_platform_id=pin.platform_id,
            expected_catalog_generation=pin.catalog_generation,
            minimum_catalog_revision=pin.minimum_catalog_revision,
            publisher_key_current=lambda digest: self.publisher_current(
                digest, pin.trust_generation,
            ),
            clock=self._now,
        )
        return provider()
