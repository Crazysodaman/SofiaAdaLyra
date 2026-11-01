"""Platform-local operational state for Core-free installations.

A ``MODULE_HOST`` installation must be able to start, own module lifecycle
state, and operate approved modules without a canonical Core database.  This
store owns exactly one Platform-local SQLite file.  It is not a second
canonical writer: it never touches ``sofia.db`` and it records an exact host
identity and role binding that is verified on every subsequent open.

Creation, identity pinning, and substitution refusal mirror the reviewed
``CanonicalSQLiteGuard`` semantics so every shared owner can use it as a
drop-in storage provider.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

from sofia.platform.config.roles import PlatformRole, PlatformRoleConfiguration
from sofia.platform.state.canonical_sqlite import (
    _reject_redirected_components,
)
from sofia.platform.state.sqlite_uri import sqlite_file_uri

LOCAL_STATE_APPLICATION_ID = 0x4C4F434C
"""'LOCL' marker, distinct from the canonical 0x534F4649."""

_HOST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


def _validate_host_identity(value: str) -> None:
    if not isinstance(value, str) or _HOST_ID.fullmatch(value) is None:
        raise ValueError("identity must be a bounded identifier")


@dataclass(frozen=True, slots=True)
class PlatformHostBinding:
    """Exact local ownership declaration verified on every open."""

    host_identity: str
    roles: tuple[PlatformRole, ...]
    core_identity: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        _validate_host_identity(self.host_identity)
        if not isinstance(self.roles, tuple) or not self.roles or any(
            not isinstance(role, PlatformRole) for role in self.roles
        ):
            raise TypeError("roles must contain PlatformRole values")
        if tuple(dict.fromkeys(self.roles)) != self.roles:
            raise ValueError("roles must be unique")
        if not self.roles:
            raise ValueError("at least one role is required")
        if PlatformRole.MODULE_HOST not in self.roles:
            raise ValueError("local module state requires the MODULE_HOST role")
        if self.core_identity is not None:
            _validate_host_identity(self.core_identity)
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")


class LocalStateUnavailable(RuntimeError):
    """The Platform-local state file is missing, unsafe, or refused ownership."""


def _absolute(path: Path | str) -> Path:
    return Path(path).absolute()


class PlatformLocalStore:
    """Own one Platform-local SQLite file with an exact host binding.

    The local file may be created by authorized Platform composition for a
    configuration that declares the ``MODULE_HOST`` role.  The store refuses
    to open when the recorded host identity or roles differ: local module
    authority must never silently adopt another host's binding.
    """

    path: Path

    def __init__(
        self, path: Path | str, *, roles: PlatformRoleConfiguration,
        host_identity: str, create: bool = True,
    ) -> None:
        if not isinstance(roles, PlatformRoleConfiguration):
            raise TypeError("roles must be a PlatformRoleConfiguration")
        _validate_host_identity(host_identity)
        if not roles.supports(PlatformRole.MODULE_HOST):
            raise PermissionError(
                "Platform-local module state requires the MODULE_HOST role"
            )
        self._roles = roles
        self._host_identity = host_identity
        self.path = _absolute(path)
        if self.path.exists() or self.path.is_symlink():
            self._identity = self._open_existing()
        elif create:
            self._identity = self._bootstrap()
        else:
            raise LocalStateUnavailable(f"local state unavailable: {self.path}")
        self._created_at, self._core_identity = self._read_binding()

    # ---- bootstrap ---------------------------------------------------------

    def _read_application_id(self, db: sqlite3.Connection) -> int:
        return int(db.execute("PRAGMA application_id").fetchone()[0])

    def _open_existing(self) -> tuple[int, int]:
        details = self.path.stat()
        if not stat.S_ISREG(details.st_mode):
            raise LocalStateUnavailable(
                f"local state is not a regular file: {self.path}"
            )
        identity = (int(details.st_dev), int(details.st_ino))
        with closing(sqlite3.connect(
            sqlite_file_uri(self.path, read_only=True),
            uri=True, timeout=10,
        )) as db:
            if self._read_application_id(db) != LOCAL_STATE_APPLICATION_ID:
                raise LocalStateUnavailable(
                    "local state file does not carry the Platform-local "
                    "application identity"
                )
        return identity

    def _bootstrap(self) -> tuple[int, int]:
        target = self.path
        _reject_redirected_components(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".bootstrap", dir=target.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        binding_moment = datetime.now(timezone.utc).isoformat()
        try:
            with closing(sqlite3.connect(str(temporary), timeout=10)) as database:
                database.execute(
                    f"PRAGMA application_id = {LOCAL_STATE_APPLICATION_ID}"
                )
                database.execute("BEGIN IMMEDIATE")
                database.execute(
                    """
                    CREATE TABLE IF NOT EXISTS platform_local_host_binding(
                        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                        host_identity TEXT NOT NULL,
                        roles_json TEXT NOT NULL,
                        core_identity TEXT,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                database.execute(
                    "INSERT INTO platform_local_host_binding VALUES(1,?,?,NULL,?)",
                    (
                        self._host_identity,
                        json.dumps(
                            [role.value for role in self._roles.roles],
                            sort_keys=True, separators=(",", ":"),
                        ),
                        binding_moment,
                    ),
                )
                database.commit()
            with temporary.open("r+b") as persisted:
                os.fsync(persisted.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                raise LocalStateUnavailable(
                    "local state appeared during bootstrap; refusing to adopt it"
                ) from None
        finally:
            temporary.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(temporary) + suffix).unlink(missing_ok=True)
        details = target.stat()
        if not stat.S_ISREG(details.st_mode):
            raise LocalStateUnavailable("local state is not a regular file")
        return (int(details.st_dev), int(details.st_ino))

    # ---- identity ----------------------------------------------------------

    def validate(self) -> Path:
        if self.path.is_symlink():
            raise LocalStateUnavailable("local state path is redirected")
        try:
            details = self.path.stat()
        except FileNotFoundError as exc:
            raise LocalStateUnavailable(
                f"local state is unavailable: {self.path}"
            ) from exc
        if not stat.S_ISREG(details.st_mode):
            raise LocalStateUnavailable("local state is not a regular file")
        identity = (int(details.st_dev), int(details.st_ino))
        if identity != self._identity:
            raise LocalStateUnavailable(
                "local state was replaced after this owner started"
            )
        return self.path

    def _read_binding(self) -> tuple[datetime, str | None]:
        with closing(self.connect()) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                """SELECT host_identity,roles_json,core_identity,created_at
                FROM platform_local_host_binding WHERE singleton=1"""
            ).fetchone()
        if row is None:
            raise LocalStateUnavailable("local host binding is missing")
        if row["host_identity"] != self._host_identity:
            raise LocalStateUnavailable(
                "local state is bound to another host identity; approved "
                "rebinding requires a separately reviewed migration"
            )
        try:
            binding = PlatformHostBinding(
                host_identity=row["host_identity"],
                roles=tuple(
                    PlatformRole(role) for role in json.loads(row["roles_json"])
                ),
                core_identity=row["core_identity"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise LocalStateUnavailable("local binding is corrupt") from exc
        if (
            tuple(dict.fromkeys(binding.roles))
            != tuple(dict.fromkeys(self._roles.roles))
        ):
            raise LocalStateUnavailable(
                "local state role binding differs from configured roles"
            )
        return binding.created_at, binding.core_identity

    @property
    def binding(self) -> PlatformHostBinding:
        return PlatformHostBinding(
            host_identity=self._host_identity, roles=self._roles.roles,
            core_identity=self._core_identity, created_at=self._created_at,
        )

    def bind_core(self, core_identity: str, *, now: datetime) -> PlatformHostBinding:
        """Bind one remote authoritative identity with compare-and-set rules.

        Binding is idempotent.  Rebinding to a different Core identity is a
        split-brain hazard and must never happen implicitly; migratings an
        installation to a different Core is a separately reviewed migration.
        """
        _validate_host_identity(core_identity)
        if not isinstance(now, datetime) or now.tzinfo is None or (
            now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        self.validate()
        with closing(self.connect()) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT core_identity FROM platform_local_host_binding "
                "WHERE singleton=1"
            ).fetchone()
            if row is None:
                raise LocalStateUnavailable("local host binding is missing")
            current = row["core_identity"]
            if current is not None and current != core_identity:
                raise LocalStateUnavailable(
                    "local state is already bound to another Core identity"
                )
            if current is None:
                changed = db.execute(
                    "UPDATE platform_local_host_binding SET core_identity=? "
                    "WHERE singleton=1 AND core_identity IS NULL",
                    (core_identity,),
                )
                if changed.rowcount != 1:
                    raise LocalStateUnavailable(
                        "local Core binding compare-and-swap failed"
                    )
        self._core_identity = core_identity
        return self.binding

    # ---- connections -------------------------------------------------------

    def connect(
        self,
        *,
        timeout: float = 10.0,
        check_same_thread: bool = True,
        factory: type[sqlite3.Connection] = sqlite3.Connection,
        read_only: bool = False,
    ) -> sqlite3.Connection:
        if type(read_only) is not bool:
            raise TypeError("read_only must be bool")
        path = self.validate()
        database = sqlite3.connect(
            sqlite_file_uri(path, read_only=read_only),
            uri=True, timeout=timeout,
            check_same_thread=check_same_thread, factory=factory,
        )
        try:
            self.validate()
        except BaseException:
            database.close()
            raise
        return database
