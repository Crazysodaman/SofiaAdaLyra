"""Typed PLAT-02 facade over the canonical State Plane and backup owners."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from sofia.platform.ops.backup import BackupEngine, BackupManifest
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.state.model import StateKey, StateRecord
from sofia.platform.state.namespaces import StateNamespaceSpec
from sofia.platform.state.plane import StateWrite
from sofia.platform.state.sqlite_plane import SQLiteStatePlane


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")


@dataclass(frozen=True, slots=True)
class NamespaceHandle:
    """A fixed namespace and privacy partition, not a permission grant."""

    spec: StateNamespaceSpec
    principal_id: str | None
    audience: str | None

    def key(self, record_key: str) -> StateKey:
        if not isinstance(record_key, str) or _ID.fullmatch(record_key) is None:
            raise ValueError("record_key must be a bounded identifier")
        return StateKey(
            self.spec.name, record_key, self.principal_id, self.audience,
        )


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    plan_id: str
    component: str
    current_revision: int
    target_revision: int
    migration_digest: str
    requires_backup: bool
    executable: bool = False


@dataclass(frozen=True, slots=True)
class RestorePlan:
    backup_id: str
    target_state_path: Path
    target_exists: bool
    requires_replacement_approval: bool
    manifest_digest: str
    executable: bool = False


class StatePlatformService:
    """One reviewed API over canonical state, lineage, backup and planning.

    Migration and restore plans are intentionally inert.  Their existence is
    evidence of checked inputs, not authority to modify canonical state.
    Execution remains with the existing separately authorized recovery tools.
    """

    def __init__(
        self,
        *,
        state_path: Path,
        namespaces: tuple[StateNamespaceSpec, ...],
        backup_engine: BackupEngine | None = None,
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if type(namespaces) is not tuple or any(
            not isinstance(item, StateNamespaceSpec) for item in namespaces
        ):
            raise TypeError("namespaces must contain StateNamespaceSpec values")
        names = [item.name for item in namespaces]
        if len(names) != len(set(names)):
            raise ValueError("namespace names must be unique")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.path = self._guard.canonical_path
        self.plane = SQLiteStatePlane(self.path)
        self.backup_engine = backup_engine
        self._specs = {item.name: item for item in namespaces}
        with closing(self._connect()) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS platform_state_namespace(
                namespace TEXT PRIMARY KEY,owner TEXT NOT NULL,state_class TEXT NOT NULL,
                principal_scoped INTEGER NOT NULL,audience_scoped INTEGER NOT NULL,
                append_only INTEGER NOT NULL,spec_digest TEXT NOT NULL,
                registered_at TEXT NOT NULL)"""
            )
            for spec in namespaces:
                encoded = self._encode_spec(spec)
                digest = sha256(encoded).hexdigest()
                row = db.execute(
                    "SELECT spec_digest FROM platform_state_namespace WHERE namespace=?",
                    (spec.name,),
                ).fetchone()
                if row is None:
                    db.execute(
                        "INSERT INTO platform_state_namespace VALUES(?,?,?,?,?,?,?,?)",
                        (spec.name, spec.owner, spec.state_class.value,
                         int(spec.principal_scoped), int(spec.audience_scoped),
                         int(spec.append_only), digest,
                         datetime.now(timezone.utc).isoformat()),
                    )
                elif row[0] != digest:
                    raise RuntimeError(
                        f"namespace {spec.name!r} changed; reviewed migration required"
                    )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode_spec(spec: StateNamespaceSpec) -> bytes:
        return json.dumps(
            {
                "append_only": spec.append_only,
                "audience_scoped": spec.audience_scoped,
                "name": spec.name,
                "owner": spec.owner,
                "principal_scoped": spec.principal_scoped,
                "state_class": spec.state_class.value,
            },
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")

    def namespace_open(
        self, namespace: str, *, principal_id: str | None, audience: str | None,
    ) -> NamespaceHandle:
        try:
            spec = self._specs[namespace]
        except KeyError as exc:
            raise LookupError("namespace is not registered by this component") from exc
        if spec.principal_scoped != (principal_id is not None):
            raise PermissionError("namespace principal scope does not match")
        if spec.audience_scoped != (audience is not None):
            raise PermissionError("namespace audience scope does not match")
        for label, value in (("principal_id", principal_id), ("audience", audience)):
            if value is not None and (
                not isinstance(value, str) or _ID.fullmatch(value) is None
            ):
                raise ValueError(f"{label} must be a bounded identifier")
        return NamespaceHandle(spec, principal_id, audience)

    def namespace_spec(self, namespace: str) -> StateNamespaceSpec:
        """Return the reviewed contract without exposing the state backend."""
        try:
            return self._specs[namespace]
        except KeyError as exc:
            raise LookupError("namespace is not registered by this component") from exc

    def write_transaction(
        self, writes: tuple[StateWrite, ...],
    ) -> tuple[StateRecord, ...]:
        for item in writes:
            spec = self._specs.get(item.record.key.namespace)
            if spec is None:
                raise PermissionError("write uses an unregistered namespace")
            if item.record.state_class is not spec.state_class:
                raise PermissionError("record state class differs from namespace contract")
            if spec.principal_scoped != (item.record.key.principal_id is not None):
                raise PermissionError("record principal scope differs from namespace contract")
            if spec.audience_scoped != (item.record.key.audience is not None):
                raise PermissionError("record audience scope differs from namespace contract")
            if spec.append_only and item.expected_revision is not None:
                raise PermissionError("append-only namespace records cannot be revised")
        return self.plane.write_transaction(writes)

    def migrate_plan(
        self, *, component: str, target_revision: int,
        migration_document: bytes,
    ) -> MigrationPlan:
        if not isinstance(component, str) or not component.strip():
            raise ValueError("component required")
        if type(target_revision) is not int or target_revision < 1:
            raise ValueError("target_revision must be positive")
        if not isinstance(migration_document, bytes) or not migration_document:
            raise ValueError("nonempty reviewed migration document required")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT current_revision FROM state_schema_component WHERE component=?",
                (component,),
            ).fetchone()
        if row is None:
            raise LookupError("component is absent from canonical schema registry")
        current = int(row[0])
        if target_revision <= current:
            raise ValueError("migration target must advance the current revision")
        digest = sha256(migration_document).hexdigest()
        return MigrationPlan(
            f"migration:{component}:{current}:{target_revision}:{digest[:16]}",
            component, current, target_revision, digest, True,
        )

    def backup(
        self, *, destination_root: Path, source_host_id: str,
        failure_domain: str, now: datetime | None = None,
    ):
        if self.backup_engine is None:
            raise RuntimeError("backup engine/key is not configured")
        return self.backup_engine.create(
            state_path=self.path, destination_root=destination_root,
            source_host_id=source_host_id, failure_domain=failure_domain,
            now=now,
        )

    def verify_backup(self, backup_dir: Path) -> BackupManifest:
        if self.backup_engine is None:
            raise RuntimeError("backup engine/key is not configured")
        return self.backup_engine.verify(backup_dir)

    def restore_plan(
        self, *, backup_dir: Path, target_state_path: Path,
    ) -> RestorePlan:
        manifest = self.verify_backup(backup_dir)
        digest = sha256(manifest.canonical_bytes()).hexdigest()
        return RestorePlan(
            manifest.backup_id, target_state_path.absolute(),
            target_state_path.exists() or target_state_path.is_symlink(),
            target_state_path.exists() or target_state_path.is_symlink(), digest,
        )

    def audit_lineage(
        self, *, namespace: str | None = None, limit: int = 100,
    ) -> tuple[dict[str, object], ...]:
        return self.plane.audit_lineage(namespace=namespace, limit=limit)
