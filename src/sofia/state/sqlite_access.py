"""Shared SQLite connection policy and content-free operation counters."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import closing, contextmanager
from pathlib import Path
import sqlite3
from threading import BoundedSemaphore, Lock, RLock
from weakref import WeakValueDictionary

from sofia.cognition.performance import record_sqlite


@dataclass(frozen=True)
class SQLiteMetrics:
    connections: int
    queries: int
    writes: int


class _ObservedConnection(sqlite3.Connection):
    def execute(self, sql, parameters=(), /):
        self._access._observe(sql)
        return super().execute(sql, parameters)

    def executemany(self, sql, seq_of_parameters, /):
        self._access._observe(sql)
        return super().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script, /):
        self._access._observe(sql_script)
        return super().executescript(sql_script)

    def close(self) -> None:
        if not getattr(self, "_access_released", False):
            self._access_released = True
            try:
                super().close()
            finally:
                self._access._readers.release()


class SQLiteAccess:
    """Per-database access policy; stores retain their own schemas/authority."""

    def __init__(self, path: Path | str, *, max_readers: int = 8) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if type(max_readers) is not int or max_readers < 1:
            raise ValueError("max_readers must be a positive integer")
        self._readers = BoundedSemaphore(max_readers)
        self.write_lock = RLock()
        self._setup_lock = Lock()
        self._wal_configured = False
        self._metrics_lock = Lock()
        self._connections = 0
        self._queries = 0
        self._writes = 0

    def connect(self, *, row_factory=None) -> sqlite3.Connection:
        self._readers.acquire()
        try:
            db = sqlite3.connect(
                str(self.path), timeout=10.0, check_same_thread=False,
                factory=_ObservedConnection,
            )
            db._access = self
            db._access_released = False
            db.row_factory = row_factory
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute("PRAGMA foreign_keys = ON")
            # journal_mode persists in the database. Avoid asking SQLite to
            # renegotiate it on every short-lived store connection.
            if not self._wal_configured:
                with self._setup_lock:
                    if not self._wal_configured:
                        db.execute("PRAGMA journal_mode = WAL")
                        self._wal_configured = True
        except Exception:
            self._readers.release()
            raise
        with self._metrics_lock:
            self._connections += 1
        return db

    def _observe(self, sql: str) -> None:
        statement = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        write = statement in {
            "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP",
            "ALTER", "VACUUM", "REINDEX", "BEGIN", "COMMIT",
        }
        with self._metrics_lock:
            self._queries += 1
            if write:
                self._writes += 1
        record_sqlite(write=write)

    def metrics(self) -> SQLiteMetrics:
        with self._metrics_lock:
            return SQLiteMetrics(self._connections, self._queries, self._writes)

    @contextmanager
    def transaction(self, *, immediate: bool = False, row_factory=None):
        """Batch one controlled commit and always release the connection."""
        lock = self.write_lock if immediate else _NullLock()
        with lock, closing(self.connect(row_factory=row_factory)) as db:
            try:
                if immediate:
                    db.execute("BEGIN IMMEDIATE")
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def verify_indexes(self, *names: str) -> tuple[str, ...]:
        with closing(self.connect()) as db:
            found = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
        return tuple(name for name in names if name not in found)


_REGISTRY_LOCK = Lock()
_REGISTRY: WeakValueDictionary[str, SQLiteAccess] = WeakValueDictionary()


def shared_sqlite_access(path: Path | str) -> SQLiteAccess:
    key = str(Path(path).resolve())
    with _REGISTRY_LOCK:
        access = _REGISTRY.get(key)
        if access is None:
            access = SQLiteAccess(key)
            _REGISTRY[key] = access
        return access


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False
