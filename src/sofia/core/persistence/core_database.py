"""Private per-Core SQLite persistence with UUID-only naming.

Each approved Core owns one independently protected directory named by its
immutable UUID.  That directory contains ``core.db`` plus the Core's continuity
record.  Display names, slugs and Core numbers never select a database path.

This module is composition, not a second memory engine.  It binds the existing
owner-scoped memory, learning, reflection and continuity services to the same
private database and UUID.  Nothing is created at import time; :meth:`create`
is an explicit installation or activation operation.

Shared Platform state (chat, inventory, governance and authentication) remains
outside these per-Core databases.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from uuid import UUID

from sofia.core.multicore.continuity import CoreContinuityStore
from sofia.core.multicore.contracts import CoreDescriptor
from sofia.core.multicore.learning import MulticoreLearningService
from sofia.core.multicore.memory import MulticoreMemoryStore
from sofia.core.multicore.reflection import MulticoreReflectionService
from sofia.platform.state.canonical_sqlite import (
    CanonicalSQLiteGuard,
    bootstrap_canonical_sqlite,
)
from sofia.platform.state.path_policy import inside_git_worktree
from sofia.platform.state.private_file import (
    assert_no_redirected_components,
    assert_not_protected_state_path,
    assert_owner_private_path,
    ensure_owner_private_directory,
    restrict_new_owner_private_path,
)
from sofia.platform.state.sqlite_uri import sqlite_file_uri

APPROVED_CORE_NUMBERS: frozenset[int] = frozenset({1, 2, 3, 6, 7})
PROHIBITED_CORE_NUMBERS: frozenset[int] = frozenset({4, 5})
CORE_DATABASE_SCHEMA = "aegis.core.private_database.v1"
CORE_DATABASE_BACKUP_SCHEMA = "aegis.core.private_database.backup.v1"
CORE_DATABASE_FILENAME = "core.db"
CORE_CONTINUITY_FILENAME = "continuity.json"
CANONICAL_APPLICATION_ID = 0x534F4649
_MAX_MANIFEST_BYTES = 65_536


class CoreDatabaseError(RuntimeError):
    """A per-Core private database contract was violated."""


class CoreDatabaseNotFound(CoreDatabaseError, FileNotFoundError):
    """The requested private Core database does not exist."""


class CoreDatabaseConflictError(CoreDatabaseError):
    """Database metadata does not belong to the requested Core."""


class CoreDatabaseIntegrityError(CoreDatabaseError):
    """A private database or backup failed integrity verification."""


class CoreDatabaseBackupError(CoreDatabaseError):
    """A backup or rollback request is unsafe or invalid."""


class CoreDatabaseDenied(PermissionError):
    """The private database boundary denied an operation."""


def _core_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        result = value
    elif isinstance(value, str) and value.strip():
        try:
            result = UUID(value)
        except ValueError:
            raise ValueError("core_id must be a UUID") from None
    else:
        raise ValueError("core_id must be a nonzero UUID")
    if result.int == 0:
        raise ValueError("core_id must be a nonzero UUID")
    return result


def _core_number(value: object) -> int:
    if type(value) is not int:
        raise TypeError("core_number must be an integer")
    if value in PROHIBITED_CORE_NUMBERS:
        raise CoreDatabaseDenied(
            f"Core #{value} is inactive or unassigned and has no private database"
        )
    if value not in APPROVED_CORE_NUMBERS:
        raise CoreDatabaseDenied(f"Core #{value} is not an approved Core")
    return value


def _absolute(value: Path | str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("private database root and backup paths must be absolute")
    return path


def _reject_protected_name(path: Path) -> None:
    assert_not_protected_state_path(path)


def _validate_safe_location(path: Path) -> None:
    _reject_protected_name(path)
    assert_no_redirected_components(path, include_leaf=True)
    if inside_git_worktree(path):
        raise CoreDatabaseDenied(
            "private Core databases and backups must remain outside a Git worktree"
        )


def _check_leaf_names(root: Path, database: Path) -> None:
    for component in (root, *root.parents, database):
        _reject_protected_name(component)


@dataclass(frozen=True, slots=True)
class CoreDatabasePaths:
    """Resolved private paths for exactly one immutable Core UUID."""

    root: Path
    core_id: UUID
    directory: Path
    database: Path
    continuity: Path

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ValueError("private database root must be absolute")
        _core_uuid(self.core_id)
        if self.directory != self.root / str(self.core_id):
            raise ValueError("private database directory is not UUID-keyed")
        if self.database != self.directory / CORE_DATABASE_FILENAME:
            raise ValueError("private database filename is not canonical")
        if self.continuity != self.directory / CORE_CONTINUITY_FILENAME:
            raise ValueError("continuity filename is not canonical")

    def safe_payload(self) -> dict[str, str]:
        return {
            "core_id": str(self.core_id),
            "directory": str(self.directory),
            "database": str(self.database),
        }


def paths_for(root: Path | str, core_id: UUID | str) -> CoreDatabasePaths:
    """Return UUID-keyed paths without creating or reading anything."""
    base = _absolute(root)
    identifier = _core_uuid(core_id)
    _validate_safe_location(base)
    directory = base / str(identifier)
    database = directory / CORE_DATABASE_FILENAME
    continuity = directory / CORE_CONTINUITY_FILENAME
    _check_leaf_names(base, database)
    _validate_safe_location(directory)
    _validate_safe_location(database)
    _validate_safe_location(continuity)
    return CoreDatabasePaths(
        root=base,
        core_id=identifier,
        directory=directory,
        database=database,
        continuity=continuity,
    )


def _ensure_private_root(root: Path) -> None:
    _validate_safe_location(root)
    if root.exists():
        if not root.is_dir():
            raise CoreDatabaseDenied("private database root is not a directory")
        assert_owner_private_path(root, directory=True)
        return
    ensure_owner_private_directory(root)
    assert_owner_private_path(root, directory=True)


def _ensure_private_core_directory(directory: Path) -> None:
    _validate_safe_location(directory)
    if directory.exists():
        if not directory.is_dir():
            raise CoreDatabaseDenied("private Core database directory is not a directory")
        assert_owner_private_path(directory, directory=True)
        return
    ensure_owner_private_directory(directory)
    assert_owner_private_path(directory, directory=True)


def _secure_private_file(path: Path) -> None:
    if os.name == "nt":
        restrict_new_owner_private_path(path, directory=False)
    else:
        path.chmod(0o600)
    assert_owner_private_path(path, directory=False)


def _read_binding(database: sqlite3.Connection) -> tuple[str, UUID, int]:
    try:
        application_id = database.execute("PRAGMA application_id").fetchone()
        rows = database.execute(
            "SELECT schema,core_id,core_number FROM core_database_metadata "
            "WHERE singleton=1"
        ).fetchall()
    except sqlite3.DatabaseError:
        raise CoreDatabaseConflictError(
            "private database has no installed Core ownership binding"
        ) from None
    if application_id is None or int(application_id[0]) != CANONICAL_APPLICATION_ID:
        raise CoreDatabaseIntegrityError(
            "private database does not carry the canonical SQLite application id"
        )
    if len(rows) != 1:
        raise CoreDatabaseIntegrityError(
            "private database ownership binding is missing or ambiguous"
        )
    schema, core_id, core_number = rows[0]
    if schema != CORE_DATABASE_SCHEMA:
        raise CoreDatabaseIntegrityError("private database schema is unsupported")
    try:
        identifier = UUID(str(core_id))
    except ValueError:
        raise CoreDatabaseIntegrityError(
            "private database ownership binding is invalid"
        ) from None
    if identifier.int == 0:
        raise CoreDatabaseIntegrityError(
            "private database ownership binding is invalid"
        )
    if type(core_number) is not int:
        raise CoreDatabaseIntegrityError(
            "private database ownership binding is invalid"
        )
    return str(schema), identifier, int(core_number)


def _verify_binding(
    database: sqlite3.Connection,
    *,
    core_id: UUID,
    core_number: int | None = None,
) -> tuple[str, UUID, int]:
    binding = _read_binding(database)
    _, stored_id, stored_number = binding
    if stored_id != core_id:
        raise CoreDatabaseConflictError(
            "private database belongs to a different Core UUID"
        )
    if core_number is not None and stored_number != core_number:
        raise CoreDatabaseConflictError(
            "private database Core number does not match the requested Core"
        )
    if stored_number in PROHIBITED_CORE_NUMBERS or (
        stored_number not in APPROVED_CORE_NUMBERS
    ):
        raise CoreDatabaseDenied(
            "private database ownership binding is not an approved Core"
        )
    return binding


def _install_binding(
    guard: CanonicalSQLiteGuard,
    *,
    core_id: UUID,
    core_number: int,
    now: datetime,
) -> None:
    with closing(guard.connect(timeout=10, check_same_thread=False)) as database, database:
        database.execute("PRAGMA busy_timeout = 10000")
        database.execute("BEGIN IMMEDIATE")
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS core_database_metadata(
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                schema TEXT NOT NULL,
                core_id TEXT NOT NULL,
                core_number INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        existing = database.execute(
            "SELECT schema,core_id,core_number FROM core_database_metadata "
            "WHERE singleton=1"
        ).fetchone()
        if existing is not None:
            schema, stored_id, stored_number = existing
            if (
                schema != CORE_DATABASE_SCHEMA
                or str(stored_id) != str(core_id)
                or int(stored_number) != core_number
            ):
                raise CoreDatabaseConflictError(
                    "private database already has a different ownership binding"
                )
            return
        database.execute(
            "INSERT INTO core_database_metadata"
            "(singleton,schema,core_id,core_number,created_at) VALUES(1,?,?,?,?)",
            (
                CORE_DATABASE_SCHEMA,
                str(core_id),
                core_number,
                now.astimezone(timezone.utc).isoformat(),
            ),
        )


@dataclass(frozen=True, slots=True)
class CoreDatabaseBackup:
    """Verified metadata for one non-destructive per-Core backup."""

    destination: Path
    core_id: UUID
    core_number: int
    created_at: datetime
    database_sha256: str
    continuity_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CoreDatabaseBackupPlan:
    """A no-write description of what a backup would produce."""

    destination: Path
    core_id: UUID
    core_number: int
    destination_available: bool
    database_bytes: int
    continuity_present: bool
    blocker: str | None = None


def _backup_paths(destination: Path) -> tuple[Path, Path, Path]:
    database = destination / CORE_DATABASE_FILENAME
    continuity = destination / CORE_CONTINUITY_FILENAME
    manifest = destination / "manifest.json"
    return database, continuity, manifest


def _validate_backup_destination(destination: Path) -> None:
    _reject_protected_name(destination)
    assert_no_redirected_components(destination, include_leaf=True)
    if inside_git_worktree(destination):
        raise CoreDatabaseDenied(
            "private Core database backups must remain outside a Git worktree"
        )
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise CoreDatabaseNotFound("backup parent directory does not exist")
    assert_no_redirected_components(destination.parent, include_leaf=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("backup destination already exists; refusing to overwrite")


def _copy_private_file(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("backup restore destination already exists")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        if os.name == "nt":
            restrict_new_owner_private_path(temporary, directory=False)
        else:
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            with source.open("rb") as content:
                shutil.copyfileobj(content, output)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise FileExistsError(
                "backup restore destination already exists; refusing to overwrite"
            ) from None
        _secure_private_file(destination)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _file_digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as content:
        for chunk in iter(lambda: content.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(destination: Path) -> dict[str, object]:
    _, _, manifest_path = _backup_paths(destination)
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise CoreDatabaseBackupError("backup manifest is missing or redirected")
    assert_no_redirected_components(manifest_path, include_leaf=True)
    assert_owner_private_path(manifest_path, directory=False)
    if manifest_path.stat().st_size > _MAX_MANIFEST_BYTES:
        raise CoreDatabaseBackupError("backup manifest is too large")
    try:
        envelope = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise CoreDatabaseBackupError("backup manifest is unreadable or corrupt") from None
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema", "payload", "sha256",
    }:
        raise CoreDatabaseBackupError("backup manifest envelope is invalid")
    payload = envelope["payload"]
    if envelope["schema"] != CORE_DATABASE_BACKUP_SCHEMA or not isinstance(payload, dict):
        raise CoreDatabaseBackupError("backup manifest envelope is invalid")
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    if not isinstance(envelope["sha256"], str) or (
        sha256(canonical.encode("utf-8")).hexdigest() != envelope["sha256"]
    ):
        raise CoreDatabaseBackupError("backup manifest integrity verification failed")
    return payload


def verify_backup(destination: Path | str) -> CoreDatabaseBackup:
    """Verify a backup without modifying it or any live Core database."""
    root = _absolute(destination)
    if not root.exists() or not root.is_dir():
        raise CoreDatabaseNotFound("backup destination does not exist")
    _validate_safe_location(root)
    assert_owner_private_path(root, directory=True)
    payload = _read_manifest(root)
    expected = {
        "core_id",
        "core_number",
        "created_at",
        "database",
        "database_sha256",
        "continuity",
        "continuity_sha256",
    }
    if set(payload) != expected:
        raise CoreDatabaseBackupError("backup manifest payload is invalid")
    try:
        core_id = UUID(str(payload["core_id"]))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
    except (TypeError, ValueError):
        raise CoreDatabaseBackupError("backup manifest identity is invalid") from None
    if type(payload["core_number"]) is not int:
        raise CoreDatabaseBackupError("backup manifest identity is invalid")
    core_number = int(payload["core_number"])
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise CoreDatabaseBackupError("backup manifest identity is invalid")
    _core_uuid(core_id)
    _core_number(core_number)
    if payload["database"] != CORE_DATABASE_FILENAME:
        raise CoreDatabaseBackupError("backup database filename is invalid")
    if payload["continuity"] not in (None, CORE_CONTINUITY_FILENAME):
        raise CoreDatabaseBackupError("backup continuity filename is invalid")
    database_path, continuity_path, _ = _backup_paths(root)
    if not database_path.is_file():
        raise CoreDatabaseBackupError("backup database is missing")
    assert_no_redirected_components(database_path, include_leaf=True)
    assert_owner_private_path(database_path, directory=False)
    if not isinstance(payload["database_sha256"], str) or (
        _file_digest(database_path) != payload["database_sha256"]
    ):
        raise CoreDatabaseBackupError("backup database integrity verification failed")
    try:
        with closing(sqlite3.connect(
            sqlite_file_uri(database_path, read_only=True), uri=True, timeout=10,
        )) as database:
            row = database.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise CoreDatabaseBackupError("backup database failed integrity_check")
            _verify_binding(database, core_id=core_id, core_number=core_number)
    except CoreDatabaseBackupError:
        raise
    except (CoreDatabaseError, sqlite3.DatabaseError) as exc:
        raise CoreDatabaseBackupError(str(exc)) from None

    continuity_digest: str | None = None
    if payload["continuity"] is None:
        if continuity_path.exists() or continuity_path.is_symlink():
            raise CoreDatabaseBackupError("backup contains an undeclared continuity file")
    else:
        if not continuity_path.is_file():
            raise CoreDatabaseBackupError("backup continuity file is missing")
        assert_no_redirected_components(continuity_path, include_leaf=True)
        assert_owner_private_path(continuity_path, directory=False)
        continuity_digest = _file_digest(continuity_path)
        if not isinstance(payload["continuity_sha256"], str) or (
            continuity_digest != payload["continuity_sha256"]
        ):
            raise CoreDatabaseBackupError(
                "backup continuity integrity verification failed"
            )
        try:
            state = CoreContinuityStore(continuity_path).load(
                expected_core_id=core_id
            )
        except Exception:
            raise CoreDatabaseBackupError(
                "backup continuity semantic verification failed"
            ) from None
        if state.core_number != core_number:
            raise CoreDatabaseBackupError(
                "backup continuity does not match the backup Core number"
            )
    return CoreDatabaseBackup(
        destination=root,
        core_id=core_id,
        core_number=core_number,
        created_at=created_at,
        database_sha256=str(payload["database_sha256"]),
        continuity_sha256=continuity_digest,
    )


class CorePrivateDatabase:
    """One Core's private SQLite database plus its bound owner-scoped services."""

    def __init__(
        self,
        paths: CoreDatabasePaths,
        guard: CanonicalSQLiteGuard,
        core_number: int,
    ) -> None:
        self._paths = paths
        self._guard = guard
        self._core_number = _core_number(core_number)
        self._closed = False
        self._memory: MulticoreMemoryStore | None = MulticoreMemoryStore(
            paths.database, paths.core_id,
        )
        self._learning: MulticoreLearningService | None = MulticoreLearningService(
            paths.database, paths.core_id,
        )
        self._reflection: MulticoreReflectionService | None = MulticoreReflectionService(
            paths.database, paths.core_id,
        )
        self._continuity = CoreContinuityStore(paths.continuity)

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        core_id: UUID | str,
        core_number: int,
        descriptor: CoreDescriptor | None = None,
        constitution_sha256: str | None = None,
        now: datetime | None = None,
    ) -> "CorePrivateDatabase":
        """Create or verify one Core's private database at installation time.

        An existing database is verified, never reinitialized.  A foreign
        ownership binding or an unbound pre-existing SQLite file fails closed.
        """
        identifier = _core_uuid(core_id)
        number = _core_number(core_number)
        if descriptor is not None:
            if constitution_sha256 is None or now is None:
                raise ValueError(
                    "continuity initialization requires constitution_sha256 and now"
                )
        elif constitution_sha256 is not None or now is not None:
            raise ValueError(
                "constitution_sha256 and now require a Core descriptor"
            )
        paths = paths_for(root, identifier)
        _ensure_private_root(paths.root)
        _ensure_private_core_directory(paths.directory)

        existed = paths.database.exists() or paths.database.is_symlink()
        if existed:
            guard = CanonicalSQLiteGuard(paths.database)
            assert_owner_private_path(paths.database, directory=False)
            with closing(guard.connect(read_only=True, timeout=10)) as database:
                _verify_binding(
                    database, core_id=identifier, core_number=number,
                )
        else:
            bootstrapped = bootstrap_canonical_sqlite(paths.database)
            guard = CanonicalSQLiteGuard(bootstrapped)
            _install_binding(
                guard,
                core_id=identifier,
                core_number=number,
                now=now or datetime.now(timezone.utc),
            )
            with closing(guard.connect(read_only=True, timeout=10)) as database:
                _verify_binding(
                    database, core_id=identifier, core_number=number,
                )
            _secure_private_file(paths.database)
        instance = cls(paths, guard, number)
        if descriptor is not None:
            try:
                instance.initialize_continuity(
                    descriptor=descriptor,
                    constitution_sha256=constitution_sha256,
                    now=now,
                )
            except BaseException:
                instance.close()
                raise
        return instance

    @classmethod
    def open(
        cls,
        root: Path | str,
        *,
        core_id: UUID | str,
        expected_core_number: int | None = None,
    ) -> "CorePrivateDatabase":
        """Open an installed Core database without creating or repairing it."""
        identifier = _core_uuid(core_id)
        number = (
            None if expected_core_number is None
            else _core_number(expected_core_number)
        )
        paths = paths_for(root, identifier)
        if not paths.root.exists() or not paths.root.is_dir():
            raise CoreDatabaseNotFound("private database root does not exist")
        assert_owner_private_path(paths.root, directory=True)
        if not paths.directory.exists() or not paths.directory.is_dir():
            raise CoreDatabaseNotFound("private Core database directory does not exist")
        assert_owner_private_path(paths.directory, directory=True)
        if not paths.database.exists() or paths.database.is_symlink():
            raise CoreDatabaseNotFound("private Core database does not exist")
        guard = CanonicalSQLiteGuard(paths.database)
        assert_owner_private_path(paths.database, directory=False)
        with closing(guard.connect(read_only=True, timeout=10)) as database:
            _, stored_id, stored_number = _verify_binding(
                database, core_id=identifier, core_number=number,
            )
        return cls(paths, guard, stored_number)

    @property
    def core_id(self) -> UUID:
        return self._paths.core_id

    @property
    def core_number(self) -> int:
        self._ensure_open()
        return self._core_number

    @property
    def paths(self) -> CoreDatabasePaths:
        self._ensure_open()
        return self._paths

    @property
    def memory_store(self) -> MulticoreMemoryStore:
        self._ensure_open()
        assert self._memory is not None
        return self._memory

    @property
    def learning_service(self) -> MulticoreLearningService:
        self._ensure_open()
        assert self._learning is not None
        return self._learning

    @property
    def reflection_service(self) -> MulticoreReflectionService:
        self._ensure_open()
        assert self._reflection is not None
        return self._reflection

    @property
    def continuity_store(self) -> CoreContinuityStore:
        self._ensure_open()
        assert self._continuity is not None
        return self._continuity

    def _ensure_open(self) -> None:
        if self._closed:
            raise CoreDatabaseError("private Core database is closed")

    def initialize_continuity(
        self,
        *,
        descriptor: CoreDescriptor,
        constitution_sha256: str,
        now: datetime,
    ):
        """Create this Core's first continuity record inside its private directory."""
        self._ensure_open()
        if not isinstance(descriptor, CoreDescriptor):
            raise TypeError("descriptor must be a CoreDescriptor")
        if descriptor.core_number != self._core_number:
            raise CoreDatabaseConflictError(
                "continuity descriptor does not match the private database Core"
            )
        if descriptor.core_id is not None and descriptor.core_id != self._paths.core_id:
            raise CoreDatabaseConflictError(
                "continuity descriptor does not match the private database UUID"
            )
        assert self._continuity is not None
        state = self._continuity.initialize(
            descriptor=descriptor,
            constitution_sha256=constitution_sha256,
            now=now,
            core_id=self._paths.core_id,
        )
        assert_owner_private_path(self._paths.continuity, directory=False)
        return state

    def verify(self, *, require_continuity: bool = False) -> bool:
        """Verify file identity, SQLite integrity, ownership and continuity."""
        self._ensure_open()
        assert self._guard is not None
        self._guard.validate()
        with closing(self._guard.connect(read_only=True, timeout=10)) as database:
            row = database.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise CoreDatabaseIntegrityError(
                    "private Core database failed SQLite integrity_check"
                )
            _verify_binding(
                database,
                core_id=self._paths.core_id,
                core_number=self._core_number,
            )
        continuity_exists = (
            self._paths.continuity.exists() or self._paths.continuity.is_symlink()
        )
        if continuity_exists:
            assert_no_redirected_components(
                self._paths.continuity, include_leaf=True,
            )
            assert_owner_private_path(self._paths.continuity, directory=False)
            assert self._continuity is not None
            state = self._continuity.load(expected_core_id=self._paths.core_id)
            if state.core_number != self._core_number:
                raise CoreDatabaseIntegrityError(
                    "continuity Core number does not match the private database"
                )
        elif require_continuity:
            raise CoreDatabaseIntegrityError(
                "private Core continuity record is missing"
            )
        return True

    def backup(
        self,
        destination: Path | str,
        *,
        dry_run: bool = False,
    ) -> CoreDatabaseBackup | CoreDatabaseBackupPlan | None:
        """Create a verified backup at a new explicit destination."""
        self._ensure_open()
        target = _absolute(destination)
        self.verify()
        database_bytes = self._paths.database.stat().st_size
        continuity_present = self._paths.continuity.is_file()
        if dry_run:
            _validate_safe_location(target)
            available = not (target.exists() or target.is_symlink())
            blocker = None
            if not available:
                blocker = "destination already exists"
            elif not target.parent.exists() or not target.parent.is_dir():
                available = False
                blocker = "backup parent directory does not exist"
            return CoreDatabaseBackupPlan(
                destination=target,
                core_id=self._paths.core_id,
                core_number=self._core_number,
                destination_available=available,
                database_bytes=database_bytes,
                continuity_present=continuity_present,
                blocker=blocker,
            )
        _validate_backup_destination(target)

        try:
            target.mkdir(mode=0o700)
        except FileExistsError:
            raise FileExistsError(
                "backup destination already exists; refusing to overwrite"
            ) from None
        try:
            if os.name == "nt":
                restrict_new_owner_private_path(target, directory=True)
            else:
                target.chmod(0o700)
            assert_owner_private_path(target, directory=True)
            backup_database, backup_continuity, _ = _backup_paths(target)
            with closing(self._guard.connect(read_only=True, timeout=10)) as source:
                self._guard.validate()
                with closing(sqlite3.connect(str(backup_database), timeout=10)) as output:
                    source.backup(output)
                    self._guard.validate()
                    row = output.execute("PRAGMA integrity_check").fetchone()
                    if row is None or row[0] != "ok":
                        raise CoreDatabaseBackupError(
                            "backup copy failed SQLite integrity_check"
                        )
                    output.commit()
                    checkpoint = output.execute(
                        "PRAGMA wal_checkpoint(TRUNCATE)"
                    ).fetchone()
                    if checkpoint is not None and checkpoint[0] != 0:
                        raise CoreDatabaseBackupError(
                            "backup copy could not checkpoint its SQLite WAL"
                        )
            _secure_private_file(backup_database)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(backup_database) + suffix).unlink(missing_ok=True)
            continuity_digest: str | None = None
            if continuity_present:
                _copy_private_file(self._paths.continuity, backup_continuity)
                continuity_digest = _file_digest(backup_continuity)
            payload = {
                "core_id": str(self._paths.core_id),
                "core_number": self._core_number,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "database": CORE_DATABASE_FILENAME,
                "database_sha256": _file_digest(backup_database),
                "continuity": (
                    CORE_CONTINUITY_FILENAME if continuity_present else None
                ),
                "continuity_sha256": continuity_digest,
            }
            canonical = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
            envelope = {
                "schema": CORE_DATABASE_BACKUP_SCHEMA,
                "payload": payload,
                "sha256": sha256(canonical.encode("utf-8")).hexdigest(),
            }
            _, _, manifest_path = _backup_paths(target)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".manifest.", suffix=".partial", dir=target,
            )
            temporary = Path(temporary_name)
            try:
                if os.name == "nt":
                    restrict_new_owner_private_path(temporary, directory=False)
                else:
                    os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                    descriptor = -1
                    handle.write(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, manifest_path)
                _secure_private_file(manifest_path)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                temporary.unlink(missing_ok=True)
            return verify_backup(target)
        except BaseException:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def rollback(
        self,
        backup: Path | str,
        destination_root: Path | str,
    ) -> "CorePrivateDatabase":
        """Restore a verified backup into a new root without touching this one.

        Rollback is staging, not live migration.  The caller must activate the
        returned database through an explicit authority boundary.
        """
        self._ensure_open()
        verified = verify_backup(backup)
        if verified.core_id != self._paths.core_id:
            raise CoreDatabaseDenied(
                "a Core cannot roll back from another Core's private backup"
            )
        target = paths_for(destination_root, self._paths.core_id)
        if target.database.exists() or target.directory.exists():
            raise FileExistsError(
                "rollback destination already exists; refusing to overwrite"
            )
        _ensure_private_root(target.root)
        _ensure_private_core_directory(target.directory)
        backup_database, backup_continuity, _ = _backup_paths(verified.destination)
        try:
            _copy_private_file(backup_database, target.database)
            if verified.continuity_sha256 is not None:
                _copy_private_file(backup_continuity, target.continuity)
            restored = CorePrivateDatabase.open(
                target.root,
                core_id=self._paths.core_id,
                expected_core_number=verified.core_number,
            )
            restored.verify(require_continuity=verified.continuity_sha256 is not None)
            return restored
        except BaseException:
            for path in (target.database, target.continuity):
                path.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(target.database) + suffix).unlink(missing_ok=True)
            try:
                target.directory.rmdir()
            except OSError:
                pass
            raise

    def close(self) -> None:
        """Release this database handle and its bound service references."""
        if self._closed:
            return
        for service in (self._memory, self._learning, self._reflection):
            if service is not None:
                try:
                    service.close()
                except Exception:
                    pass
        self._memory = None
        self._learning = None
        self._reflection = None
        self._continuity = None
        self._guard = None
        self._closed = True

    def __enter__(self) -> "CorePrivateDatabase":
        self._ensure_open()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


class CorePrivateDatabaseCatalog:
    """In-memory catalog of explicitly opened per-Core private databases."""

    def __init__(self, root: Path | str) -> None:
        self._root = _absolute(root)
        _validate_safe_location(self._root)
        self._databases: dict[UUID, CorePrivateDatabase] = {}
        self._closed = False

    @property
    def root(self) -> Path:
        return self._root

    def create(
        self,
        *,
        core_id: UUID | str,
        core_number: int,
        descriptor: CoreDescriptor | None = None,
        constitution_sha256: str | None = None,
        now: datetime | None = None,
    ) -> CorePrivateDatabase:
        self._ensure_open()
        identifier = _core_uuid(core_id)
        database = CorePrivateDatabase.create(
            self._root,
            core_id=identifier,
            core_number=core_number,
            descriptor=descriptor,
            constitution_sha256=constitution_sha256,
            now=now,
        )
        existing = self._databases.get(identifier)
        if existing is not None and existing is not database:
            existing.close()
        self._databases[identifier] = database
        return database

    def open(
        self,
        *,
        core_id: UUID | str,
        expected_core_number: int | None = None,
    ) -> CorePrivateDatabase:
        self._ensure_open()
        identifier = _core_uuid(core_id)
        existing = self._databases.get(identifier)
        if existing is not None:
            if existing._closed:
                self._databases.pop(identifier, None)
            else:
                if (
                    expected_core_number is not None
                    and existing.core_number != expected_core_number
                ):
                    raise CoreDatabaseConflictError(
                        "open Core number does not match the cached private database"
                    )
                return existing
        database = CorePrivateDatabase.open(
            self._root,
            core_id=identifier,
            expected_core_number=expected_core_number,
        )
        self._databases[identifier] = database
        return database

    def get(self, core_id: UUID | str) -> CorePrivateDatabase | None:
        self._ensure_open()
        return self._databases.get(_core_uuid(core_id))

    def databases(self) -> tuple[CorePrivateDatabase, ...]:
        self._ensure_open()
        return tuple(self._databases.values())

    def _ensure_open(self) -> None:
        if self._closed:
            raise CoreDatabaseError("private Core database catalog is closed")

    def close(self) -> None:
        if self._closed:
            return
        for database in self._databases.values():
            database.close()
        self._databases.clear()
        self._closed = True

    def __enter__(self) -> "CorePrivateDatabaseCatalog":
        self._ensure_open()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


__all__ = [
    "APPROVED_CORE_NUMBERS",
    "CANONICAL_APPLICATION_ID",
    "CORE_CONTINUITY_FILENAME",
    "CORE_DATABASE_BACKUP_SCHEMA",
    "CORE_DATABASE_FILENAME",
    "CORE_DATABASE_SCHEMA",
    "CoreDatabaseBackup",
    "CoreDatabaseBackupError",
    "CoreDatabaseBackupPlan",
    "CoreDatabaseConflictError",
    "CoreDatabaseDenied",
    "CoreDatabaseError",
    "CoreDatabaseIntegrityError",
    "CoreDatabaseNotFound",
    "CoreDatabasePaths",
    "CorePrivateDatabase",
    "CorePrivateDatabaseCatalog",
    "PROHIBITED_CORE_NUMBERS",
    "paths_for",
    "verify_backup",
]
