"""Durable, content-addressed evidence for authorized source inspection."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .model import CodebaseInspectionEvidence


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("inspection timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CodebaseInspectionRecord:
    inspection_id: str
    snapshot_digest: str
    root: str
    observed_at: datetime
    fresh_until: datetime
    file_count: int
    python_module_count: int
    file_limit_reached: bool
    added_paths: tuple[str, ...]
    modified_paths: tuple[str, ...]
    removed_paths: tuple[str, ...]
    capability_modules_added: tuple[str, ...]
    capability_modules_removed: tuple[str, ...]


class CodebaseInspectionStore:
    """Append-only inspection runs in canonical state; never source content."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS core_codebase_inspection(
                    inspection_id TEXT PRIMARY KEY,snapshot_digest TEXT NOT NULL,
                    root TEXT NOT NULL,observed_at TEXT NOT NULL,fresh_until TEXT NOT NULL,
                    file_count INTEGER NOT NULL,python_module_count INTEGER NOT NULL,
                    file_limit_reached INTEGER NOT NULL CHECK(file_limit_reached IN (0,1)),
                    added_json TEXT NOT NULL,modified_json TEXT NOT NULL,
                    removed_json TEXT NOT NULL,capabilities_added_json TEXT NOT NULL,
                    capabilities_removed_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS core_codebase_inspection_recent
                    ON core_codebase_inspection(observed_at DESC,inspection_id DESC);
                CREATE TABLE IF NOT EXISTS core_codebase_inspection_file(
                    inspection_id TEXT NOT NULL,relative_path TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,size_bytes INTEGER NOT NULL,
                    PRIMARY KEY(inspection_id,relative_path));
                CREATE TABLE IF NOT EXISTS core_codebase_inspection_module(
                    inspection_id TEXT NOT NULL,module_name TEXT NOT NULL,
                    PRIMARY KEY(inspection_id,module_name));
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _record(row: sqlite3.Row) -> CodebaseInspectionRecord:
        return CodebaseInspectionRecord(
            row["inspection_id"], row["snapshot_digest"], row["root"],
            datetime.fromisoformat(row["observed_at"]),
            datetime.fromisoformat(row["fresh_until"]), int(row["file_count"]),
            int(row["python_module_count"]), bool(row["file_limit_reached"]),
            tuple(json.loads(row["added_json"])),
            tuple(json.loads(row["modified_json"])),
            tuple(json.loads(row["removed_json"])),
            tuple(json.loads(row["capabilities_added_json"])),
            tuple(json.loads(row["capabilities_removed_json"])),
        )

    def latest(self) -> CodebaseInspectionRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM core_codebase_inspection "
                "ORDER BY observed_at DESC,inspection_id DESC LIMIT 1"
            ).fetchone()
        return None if row is None else self._record(row)

    def record(
        self, evidence: CodebaseInspectionEvidence, *, observed_at: datetime,
        freshness: timedelta = timedelta(hours=6),
    ) -> CodebaseInspectionRecord:
        if not isinstance(evidence, CodebaseInspectionEvidence):
            raise TypeError("evidence must be CodebaseInspectionEvidence")
        moment = _utc(observed_at)
        if not isinstance(freshness, timedelta) or not (
            timedelta(minutes=1) <= freshness <= timedelta(days=7)
        ):
            raise ValueError("freshness must be 1 minute..7 days")
        root = evidence.root.resolve()
        files: dict[str, tuple[str, int]] = {}
        for item in evidence.files:
            if item.content_sha256 is None:
                raise ValueError("durable inspection requires content hashes")
            try:
                relative = item.path.resolve().relative_to(root).as_posix()
            except ValueError as exc:
                raise ValueError("inspection file escaped authorized root") from exc
            files[relative] = (item.content_sha256, item.size_bytes)
        modules = tuple(sorted(item.module_name for item in evidence.python_modules))
        document = {
            "files": [(path, *files[path]) for path in sorted(files)],
            "modules": modules,
            "limited": evidence.file_limit_reached,
        }
        digest = sha256(
            json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT inspection_id FROM core_codebase_inspection "
                "ORDER BY observed_at DESC,inspection_id DESC LIMIT 1"
            ).fetchone()
            old_files: dict[str, str] = {}
            old_modules: set[str] = set()
            if previous is not None:
                old_files = {
                    row[0]: row[1] for row in db.execute(
                        "SELECT relative_path,content_sha256 "
                        "FROM core_codebase_inspection_file WHERE inspection_id=?",
                        (previous[0],),
                    )
                }
                old_modules = {
                    row[0] for row in db.execute(
                        "SELECT module_name FROM core_codebase_inspection_module "
                        "WHERE inspection_id=?",
                        (previous[0],),
                    )
                }
            added = tuple(sorted(set(files) - set(old_files)))
            removed = tuple(sorted(set(old_files) - set(files)))
            modified = tuple(sorted(
                path for path in set(files) & set(old_files)
                if files[path][0] != old_files[path]
            ))
            module_set = set(modules)
            modules_added = tuple(sorted(module_set - old_modules))
            modules_removed = tuple(sorted(old_modules - module_set))
            inspection_id = f"codeinspect:{uuid4()}"
            values = tuple(
                json.dumps(list(value), separators=(",", ":"))
                for value in (added, modified, removed, modules_added, modules_removed)
            )
            db.execute(
                "INSERT INTO core_codebase_inspection VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (inspection_id, digest, str(root), moment.isoformat(),
                 (moment + freshness).isoformat(), len(files), len(modules),
                 int(evidence.file_limit_reached), *values),
            )
            db.executemany(
                "INSERT INTO core_codebase_inspection_file VALUES(?,?,?,?)",
                ((inspection_id, path, value[0], value[1])
                 for path, value in sorted(files.items())),
            )
            db.executemany(
                "INSERT INTO core_codebase_inspection_module VALUES(?,?)",
                ((inspection_id, name) for name in modules),
            )
            row = db.execute(
                "SELECT * FROM core_codebase_inspection WHERE inspection_id=?",
                (inspection_id,),
            ).fetchone()
        return self._record(row)
