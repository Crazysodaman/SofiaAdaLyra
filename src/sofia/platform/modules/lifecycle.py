"""Canonical, revisioned lifecycle for verified Sofía module packages."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import Callable

from sofia.platform.capability.model import Capability
from sofia.platform.capability.system import CapabilityHandler, CapabilitySystem
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .compatibility import ModuleCompatibilityReport
from .package import (
    OperationProfileKind,
    VerifiedModulePackage,
    parse_signed_manifest,
)


class ModuleLifecycle(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    STAGED = "staged"
    INSTALLED_DISABLED = "installed_disabled"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DRAINING = "draining"
    PAUSED = "paused"
    QUARANTINED = "quarantined"
    UPDATING = "updating"
    ROLLING_BACK = "rolling_back"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class ModuleLifecycleRecord:
    module_id: str
    version: str
    package_digest: str
    lifecycle: ModuleLifecycle
    revision: int
    active_profile: OperationProfileKind | None
    staged_path: str | None
    reason: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ModuleInstallPlan:
    module_id: str
    version: str
    package_digest: str
    dependencies: tuple[str, ...]
    target_profile: OperationProfileKind
    required_authority: str
    executable: bool = False


@dataclass(frozen=True, slots=True)
class ModuleChangePlan:
    module_id: str
    current_version: str
    target_version: str | None
    operation: str
    required_authority: str
    executable: bool = False


@dataclass(frozen=True, slots=True)
class ModuleLifecycleHealth:
    module_id: str
    lifecycle: ModuleLifecycle
    healthy: bool
    ready: bool
    reason: str
    revision: int


@dataclass(frozen=True, slots=True)
class ModuleTransitionReceipt:
    event_id: int
    module_id: str
    from_lifecycle: ModuleLifecycle | None
    to_lifecycle: ModuleLifecycle
    revision: int
    operation_ref: str
    actor: str
    reason: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ModuleLifecycleAuthorization:
    """Exact, inert lifecycle operation presented to the authority boundary."""

    operation: str
    module_id: str
    version: str
    package_digest: str
    expected_revision: int
    target_lifecycle: ModuleLifecycle
    operation_ref: str
    actor: str
    occurred_at: datetime
    profile: OperationProfileKind | None = None

    def __post_init__(self) -> None:
        if self.operation not in {
            "approve", "stage", "activate", "resume", "pause", "disable",
            "quarantine", "update", "rollback", "remove",
        }:
            raise ValueError("unsupported module lifecycle operation")
        for label, value in (
            ("module_id", self.module_id),
            ("version", self.version),
            ("package_digest", self.package_digest),
            ("operation_ref", self.operation_ref),
            ("actor", self.actor),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if type(self.expected_revision) is not int or self.expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if not isinstance(self.target_lifecycle, ModuleLifecycle):
            raise TypeError("target_lifecycle must be ModuleLifecycle")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("occurred_at must be timezone-aware")
        if self.profile is not None and not isinstance(
            self.profile, OperationProfileKind
        ):
            raise TypeError("profile must be OperationProfileKind or None")

    @property
    def capability(self) -> str:
        return f"module.{self.operation}"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "module_id": self.module_id,
            "version": self.version,
            "package_digest": self.package_digest,
            "expected_revision": self.expected_revision,
            "target_lifecycle": self.target_lifecycle.value,
            "profile": None if self.profile is None else self.profile.value,
        }


LifecycleAuthorizer = Callable[[ModuleLifecycleAuthorization], bool]


class ModuleLifecycleManager:
    """Persist module state and register capabilities only after authorization."""

    def __init__(self, *, state_path: Path, store_root: Path,
                 capability_system: CapabilitySystem,
                 authorizer: LifecycleAuthorizer) -> None:
        if not isinstance(state_path, Path) or not isinstance(store_root, Path):
            raise TypeError("state_path and store_root must be Path")
        if not isinstance(capability_system, CapabilitySystem):
            raise TypeError("capability_system must be CapabilitySystem")
        if not callable(authorizer):
            raise TypeError("authorizer must be callable")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.store_root = store_root.absolute()
        self.capability_system = capability_system
        self.authorizer = authorizer
        self._active_batches: dict[
            str, tuple[tuple[Capability, CapabilityHandler], ...]
        ] = {}
        for component in (self.store_root, *self.store_root.parents):
            if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
                raise RuntimeError("module store path cannot be redirected")
        self.store_root.mkdir(parents=True, exist_ok=True)
        if self.store_root.is_symlink():
            raise RuntimeError("module store root cannot be redirected")
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_module_lifecycle(
                    module_id TEXT PRIMARY KEY,version TEXT NOT NULL,
                    package_digest TEXT NOT NULL,lifecycle TEXT NOT NULL,
                    revision INTEGER NOT NULL,active_profile TEXT,staged_path TEXT,
                    reason TEXT NOT NULL,updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS platform_module_lifecycle_event(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,module_id TEXT NOT NULL,
                    from_lifecycle TEXT,to_lifecycle TEXT NOT NULL,
                    revision INTEGER NOT NULL,operation_ref TEXT NOT NULL,
                    actor TEXT NOT NULL,reason TEXT NOT NULL,occurred_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS platform_module_release_history(
                    module_id TEXT NOT NULL,package_digest TEXT NOT NULL,
                    version TEXT NOT NULL,staged_path TEXT,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(module_id,package_digest));
                CREATE TABLE IF NOT EXISTS platform_module_dependency(
                    module_id TEXT NOT NULL,dependency_id TEXT NOT NULL,
                    minimum_version TEXT NOT NULL,maximum_version_exclusive TEXT,
                    PRIMARY KEY(module_id,dependency_id));
                CREATE TABLE IF NOT EXISTS platform_module_capability(
                    module_id TEXT NOT NULL,capability_id TEXT NOT NULL,
                    schema_ref TEXT NOT NULL,
                    PRIMARY KEY(module_id,capability_id));
                CREATE TABLE IF NOT EXISTS platform_module_policy(
                    module_id TEXT PRIMARY KEY,package_digest TEXT NOT NULL,
                    placement_mode TEXT NOT NULL,isolation_profile TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS platform_module_manifest_projection(
                    module_id TEXT PRIMARY KEY,package_digest TEXT NOT NULL,
                    manifest_json TEXT NOT NULL);
                """
            )
            rows = db.execute(
                """SELECT module_id,lifecycle,revision FROM platform_module_lifecycle
                WHERE lifecycle IN ('active','activating','draining','updating','rolling_back')"""
            ).fetchall()
            moment = datetime.now(timezone.utc).isoformat()
            for row in rows:
                target = (
                    ModuleLifecycle.PAUSED
                    if row["lifecycle"] == ModuleLifecycle.ACTIVE.value
                    else ModuleLifecycle.QUARANTINED
                )
                revision = int(row["revision"]) + 1
                db.execute(
                    """UPDATE platform_module_lifecycle SET lifecycle=?,revision=?,
                    reason='runtime restarted; adapter requires reconciliation',
                    updated_at=? WHERE module_id=? AND revision=?""",
                    (target.value, revision, moment, row["module_id"], row["revision"]),
                )
                db.execute(
                    "INSERT INTO platform_module_lifecycle_event VALUES(NULL,?,?,?,?,?,?,?,?)",
                    (row["module_id"], row["lifecycle"], target.value, revision,
                     "startup:reconcile", "platform:runtime",
                     "adapter authority was not assumed across restart", moment),
                )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _manifest_projection(package: VerifiedModulePackage) -> tuple[str, str, str]:
        """Return the identity-bound signed policy projection (not authority).

        The signature is intentionally omitted because the lifecycle already
        stores the verified complete-manifest digest.  This projection exists
        so diagnostics do not lose resource, profile, device, and maintenance
        policy after package admission.
        """
        document = package.manifest.unsigned_document()
        encoded = json.dumps(
            document, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        if sha256(encoded.encode("utf-8")).hexdigest() != package.package_digest:
            raise RuntimeError("module manifest projection identity mismatch")
        return package.manifest.module_id, package.package_digest, encoded

    def _persist_manifest_projection(
        self, db: sqlite3.Connection, package: VerifiedModulePackage, *,
        replace_existing: bool,
    ) -> None:
        projected = self._manifest_projection(package)
        if replace_existing:
            db.execute(
                "INSERT INTO platform_module_manifest_projection VALUES(?,?,?) "
                "ON CONFLICT(module_id) DO UPDATE SET "
                "package_digest=excluded.package_digest,"
                "manifest_json=excluded.manifest_json",
                projected,
            )
            return
        db.execute(
            "INSERT OR IGNORE INTO platform_module_manifest_projection "
            "VALUES(?,?,?)",
            projected,
        )
        stored = db.execute(
            "SELECT package_digest,manifest_json "
            "FROM platform_module_manifest_projection WHERE module_id=?",
            (projected[0],),
        ).fetchone()
        if stored is None or tuple(stored) != projected[1:]:
            raise RuntimeError(
                "canonical module manifest projection conflicts with verified package"
            )

    @staticmethod
    def _assert_unredirected(path: Path, root: Path) -> None:
        current = path
        while True:
            if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
                raise RuntimeError("immutable module path is redirected")
            if current == root:
                return
            if root not in current.parents:
                raise RuntimeError("immutable module path escapes store root")
            current = current.parent

    @classmethod
    def _stored_files(cls, destination: Path) -> frozenset[str]:
        result: set[str] = set()
        pending = [destination]
        while pending:
            directory = pending.pop()
            cls._assert_unredirected(directory, destination)
            for child in directory.iterdir():
                cls._assert_unredirected(child, destination)
                if child.is_dir():
                    pending.append(child)
                elif child.is_file():
                    result.add(child.relative_to(destination).as_posix())
                else:
                    raise RuntimeError("immutable module store contains unsupported entry")
        return frozenset(result)

    @staticmethod
    def _record(row: sqlite3.Row) -> ModuleLifecycleRecord:
        return ModuleLifecycleRecord(
            row["module_id"], row["version"], row["package_digest"],
            ModuleLifecycle(row["lifecycle"]), int(row["revision"]),
            None if row["active_profile"] is None else OperationProfileKind(row["active_profile"]),
            row["staged_path"], row["reason"], datetime.fromisoformat(row["updated_at"]),
        )

    def describe(self, module_id: str) -> ModuleLifecycleRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_module_lifecycle WHERE module_id=?",
                (module_id,),
            ).fetchone()
        return None if row is None else self._record(row)

    def reopen_staged_package(self, module_id: str) -> VerifiedModulePackage:
        """Reopen an already verified immutable bundle without importing it.

        Publisher trust was established before staging. Restart recovery
        rechecks canonical manifest identity, exact file set and every artifact
        digest; it does not accept a new path or dynamically execute package
        code.
        """
        current = self.describe(module_id)
        if current is None or current.staged_path is None:
            raise LookupError("module has no staged immutable package")
        root = Path(current.staged_path)
        self._assert_unredirected(root, self.store_root)
        if not root.is_dir() or root.parent != self.store_root:
            raise RuntimeError("staged module path is unavailable or relocated")
        manifest_path = root / "manifest.v1.json"
        self._assert_unredirected(manifest_path, root)
        try:
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("staged module manifest is unreadable") from exc
        manifest = parse_signed_manifest(document)
        if (
            manifest.module_id != current.module_id
            or manifest.version != current.version
            or manifest.package_identity_digest() != current.package_digest
        ):
            raise RuntimeError("staged package identity differs from lifecycle")
        expected_files = {
            relative for relative, _ in manifest.artifact_digests
        } | {"manifest.v1.json"}
        if self._stored_files(root) != frozenset(expected_files):
            raise RuntimeError("staged package file set changed")
        for relative, expected_digest in manifest.artifact_digests:
            target = root / relative
            self._assert_unredirected(target, root)
            if sha256(target.read_bytes()).hexdigest() != expected_digest:
                raise RuntimeError("staged package artifact digest changed")
        return VerifiedModulePackage(manifest, root, current.package_digest)

    @staticmethod
    def _receipt(row: sqlite3.Row) -> ModuleTransitionReceipt:
        return ModuleTransitionReceipt(
            event_id=int(row["event_id"]),
            module_id=str(row["module_id"]),
            from_lifecycle=(
                None
                if row["from_lifecycle"] is None
                else ModuleLifecycle(str(row["from_lifecycle"]))
            ),
            to_lifecycle=ModuleLifecycle(str(row["to_lifecycle"])),
            revision=int(row["revision"]),
            operation_ref=str(row["operation_ref"]),
            actor=str(row["actor"]),
            reason=str(row["reason"]),
            occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        )

    def transition_receipt(
        self, module_id: str, revision: int,
    ) -> ModuleTransitionReceipt:
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("module_id required")
        if type(revision) is not int or revision < 1:
            raise ValueError("revision must be a positive integer")
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_module_lifecycle_event "
                "WHERE module_id=? AND revision=? ORDER BY event_id DESC LIMIT 1",
                (module_id, revision),
            ).fetchone()
        if row is None:
            raise LookupError("module lifecycle transition receipt does not exist")
        return self._receipt(row)

    def history(
        self, module_id: str, *, limit: int = 100,
    ) -> tuple[ModuleTransitionReceipt, ...]:
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("module_id required")
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("limit must be in 1..500")
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM platform_module_lifecycle_event "
                "WHERE module_id=? ORDER BY revision DESC,event_id DESC LIMIT ?",
                (module_id, limit),
            ).fetchall()
        return tuple(self._receipt(row) for row in rows)

    def discover(self, package: VerifiedModulePackage, *, now: datetime) -> ModuleLifecycleRecord:
        if not isinstance(package, VerifiedModulePackage):
            raise TypeError("verified package required")
        moment = now.astimezone(timezone.utc)
        current = self.describe(package.manifest.module_id)
        if current is not None:
            if current.package_digest != package.package_digest:
                raise RuntimeError("module identity already refers to another package")
            # Older canonical databases predate the signed policy projection.
            # The already verified exact package can backfill only its own
            # matching row; conflicting policy remains a hard failure.
            expected_policy = (
                package.package_digest,
                package.manifest.placement_mode.value,
                package.manifest.isolation_profile,
            )
            with closing(self._connect()) as db, db:
                db.execute(
                    "INSERT OR IGNORE INTO platform_module_policy "
                    "VALUES(?,?,?,?)",
                    (package.manifest.module_id, *expected_policy),
                )
                policy = db.execute(
                    "SELECT package_digest,placement_mode,isolation_profile "
                    "FROM platform_module_policy WHERE module_id=?",
                    (package.manifest.module_id,),
                ).fetchone()
                self._persist_manifest_projection(
                    db, package, replace_existing=False,
                )
            if policy is None or tuple(policy) != expected_policy:
                raise RuntimeError(
                    "canonical module policy conflicts with verified package"
                )
            return current
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO platform_module_lifecycle VALUES(?,?,?,?,1,NULL,NULL,?,?)",
                (package.manifest.module_id, package.manifest.version,
                 package.package_digest, ModuleLifecycle.VALIDATED.value,
                 "signature and artifacts verified", moment.isoformat()),
            )
            db.execute(
                "INSERT INTO platform_module_lifecycle_event VALUES(NULL,?,?,?,?,?,?,?,?)",
                (package.manifest.module_id, None, ModuleLifecycle.VALIDATED.value,
                 1, "verification:package", "platform:verifier",
                 "signature and artifacts verified", moment.isoformat()),
            )
            db.executemany(
                "INSERT INTO platform_module_dependency VALUES(?,?,?,?)",
                tuple((package.manifest.module_id, item.module_id,
                       item.minimum_version, item.maximum_version_exclusive)
                      for item in package.manifest.dependencies),
            )
            db.executemany(
                "INSERT INTO platform_module_capability VALUES(?,?,?)",
                tuple(
                    (package.manifest.module_id, capability_id, schema_ref)
                    for capability_id, schema_ref
                    in package.manifest.capability_schemas
                ),
            )
            db.execute(
                "INSERT INTO platform_module_policy VALUES(?,?,?,?)",
                (
                    package.manifest.module_id,
                    package.package_digest,
                    package.manifest.placement_mode.value,
                    package.manifest.isolation_profile,
                ),
            )
            self._persist_manifest_projection(
                db, package, replace_existing=False,
            )
        return self.describe(package.manifest.module_id)  # type: ignore[return-value]

    def plan_install(self, package: VerifiedModulePackage,
                     *, profile: OperationProfileKind) -> ModuleInstallPlan:
        if profile not in {item.profile_id for item in package.manifest.profiles}:
            raise ValueError("profile is not declared by signed manifest")
        return ModuleInstallPlan(
            package.manifest.module_id, package.manifest.version,
            package.package_digest,
            tuple(item.module_id for item in package.manifest.dependencies),
            profile, "module.install", False,
        )

    def plan_update(self, current_module_id: str,
                    package: VerifiedModulePackage) -> ModuleChangePlan:
        current = self.describe(current_module_id)
        if current is None:
            raise LookupError("unknown module")
        if package.manifest.module_id != current_module_id:
            raise ValueError("update package identity differs from installed module")
        if package.package_digest == current.package_digest:
            raise ValueError("update package is identical to installed package")
        return ModuleChangePlan(
            current_module_id, current.version, package.manifest.version,
            "update", "module.update", False,
        )

    def plan_remove(self, module_id: str) -> ModuleChangePlan:
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        return ModuleChangePlan(
            module_id, current.version, None, "remove", "module.remove", False,
        )

    def health(self, module_id: str) -> ModuleLifecycleHealth:
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        healthy = current.lifecycle in {
            ModuleLifecycle.STAGED, ModuleLifecycle.INSTALLED_DISABLED,
            ModuleLifecycle.ACTIVE, ModuleLifecycle.PAUSED,
        }
        reason = current.reason
        # Lifecycle labels are historical records, not proof the immutable
        # signed package still exists or has the original bytes. Do not
        # certify a tampered staged bundle as healthy after a restart.
        if current.lifecycle is ModuleLifecycle.STAGED:
            try:
                self.reopen_staged_package(module_id)
            except (OSError, UnicodeError, ValueError, RuntimeError, LookupError) as error:
                healthy = False
                reason = f"staged package verification failed: {type(error).__name__}"
        return ModuleLifecycleHealth(
            module_id, current.lifecycle, healthy,
            current.lifecycle is ModuleLifecycle.ACTIVE and healthy, reason,
            current.revision,
        )

    def _authorize(
        self, *, operation: str, current: ModuleLifecycleRecord,
        expected_revision: int, target: ModuleLifecycle, operation_ref: str,
        actor: str, now: datetime, profile: OperationProfileKind | None = None,
        package: VerifiedModulePackage | None = None,
    ) -> None:
        selected = package.manifest if package is not None else None
        request = ModuleLifecycleAuthorization(
            operation=operation,
            module_id=current.module_id,
            version=current.version if selected is None else selected.version,
            package_digest=(
                current.package_digest
                if package is None else package.package_digest
            ),
            expected_revision=expected_revision,
            target_lifecycle=target,
            operation_ref=operation_ref,
            actor=actor,
            occurred_at=now.astimezone(timezone.utc),
            profile=profile,
        )
        if not self.authorizer(request):
            raise PermissionError("module lifecycle operation is not authorized")

    def _transition(self, module_id: str, *, expected_revision: int,
                    allowed: tuple[ModuleLifecycle, ...], target: ModuleLifecycle,
                    operation_ref: str, actor: str, reason: str, now: datetime,
                    staged_path: str | None = None,
                    active_profile: OperationProfileKind | None = None,
                    authorization_operation: str | None = None,
                    authorized: bool = True) -> ModuleLifecycleRecord:
        moment = now.astimezone(timezone.utc)
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        if authorized:
            self._authorize(
                operation=authorization_operation or target.value,
                current=current, expected_revision=expected_revision,
                target=target, operation_ref=operation_ref, actor=actor,
                now=moment, profile=active_profile,
            )
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM platform_module_lifecycle WHERE module_id=?",
                (module_id,),
            ).fetchone()
            if row is None:
                raise LookupError("unknown module")
            current = self._record(row)
            if current.revision != expected_revision or current.lifecycle not in allowed:
                raise RuntimeError("module lifecycle revision/state changed")
            revision = expected_revision + 1
            changed = db.execute(
                """UPDATE platform_module_lifecycle SET lifecycle=?,revision=?,
                active_profile=?,staged_path=COALESCE(?,staged_path),reason=?,updated_at=?
                WHERE module_id=? AND revision=?""",
                (target.value, revision,
                 None if active_profile is None else active_profile.value,
                 staged_path, reason[:500], moment.isoformat(), module_id,
                 expected_revision),
            )
            if changed.rowcount != 1:
                raise RuntimeError("module lifecycle compare-and-swap failed")
            db.execute(
                "INSERT INTO platform_module_lifecycle_event VALUES(NULL,?,?,?,?,?,?,?,?)",
                (module_id, current.lifecycle.value, target.value, revision,
                 operation_ref, actor, reason[:500], moment.isoformat()),
            )
        return self.describe(module_id)  # type: ignore[return-value]

    def approve(self, module_id: str, *, expected_revision: int,
                operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        return self._transition(
            module_id, expected_revision=expected_revision,
            allowed=(ModuleLifecycle.VALIDATED, ModuleLifecycle.REVIEW_PENDING),
            target=ModuleLifecycle.APPROVED, operation_ref=operation_ref,
            actor=actor, reason="package approved for staging", now=now,
            authorization_operation="approve",
        )

    def _store_package(self, package: VerifiedModulePackage) -> tuple[Path, bool]:
        destination = self.store_root / package.package_digest
        if destination.is_symlink():
            raise RuntimeError("immutable module destination is redirected")
        newly_created = not destination.exists()
        if newly_created:
            destination.mkdir()
        try:
            self._assert_unredirected(destination, self.store_root)
            expected_files = {
                relative for relative, _ in package.manifest.artifact_digests
            } | {"manifest.v1.json"}
            existing_files = self._stored_files(destination)
            if not existing_files.issubset(expected_files):
                raise RuntimeError("staged package contains undeclared files")
            for relative, expected in package.manifest.artifact_digests:
                source = package.package_root / relative
                target = destination / relative
                data = source.read_bytes()
                if sha256(data).hexdigest() != expected:
                    raise RuntimeError("source package changed after verification")
                if target.exists():
                    if target.is_symlink() or sha256(target.read_bytes()).hexdigest() != expected:
                        raise RuntimeError("staged package conflicts with verified identity")
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self._assert_unredirected(target.parent, destination)
                    with target.open("xb") as handle:
                        handle.write(data)
                        handle.flush()
                        os.fsync(handle.fileno())
            manifest_path = destination / "manifest.v1.json"
            document = dict(package.manifest.unsigned_document())
            document["signature_b64"] = package.manifest.signature_b64
            manifest_bytes = json.dumps(
                document, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
            if not manifest_path.exists():
                with manifest_path.open("xb") as handle:
                    handle.write(manifest_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
            elif manifest_path.is_symlink():
                raise RuntimeError("staged manifest is redirected")
            elif manifest_path.read_bytes() != manifest_bytes:
                raise RuntimeError("staged manifest conflicts with verified identity")
            if self._stored_files(destination) != frozenset(expected_files):
                raise RuntimeError("staged package file set is incomplete")
        except BaseException:
            if newly_created:
                import shutil
                shutil.rmtree(destination, ignore_errors=True)
            raise
        return destination, newly_created

    def stage(self, package: VerifiedModulePackage, *, expected_revision: int,
              operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        current = self.describe(package.manifest.module_id)
        if current is None or current.package_digest != package.package_digest:
            raise RuntimeError("verified package differs from lifecycle record")
        self._authorize(
            operation="stage", current=current,
            expected_revision=expected_revision, target=ModuleLifecycle.STAGED,
            operation_ref=operation_ref, actor=actor, now=now, package=package,
        )
        destination, newly_created = self._store_package(package)
        try:
            return self._transition(
                current.module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.APPROVED,), target=ModuleLifecycle.STAGED,
                operation_ref=operation_ref, actor=actor,
                reason="immutable verified package staged", now=now,
                staged_path=str(destination), authorized=False,
            )
        except BaseException:
            if newly_created:
                import shutil
                shutil.rmtree(destination, ignore_errors=True)
            raise

    def activate(self, package: VerifiedModulePackage, *, expected_revision: int,
                 profile: OperationProfileKind,
                 compatibility: ModuleCompatibilityReport,
                 registrations: tuple[tuple[Capability, CapabilityHandler], ...],
                 operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        activating = self.begin_activation(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=operation_ref, actor=actor, now=now,
        )
        return self.complete_activation(
            package, expected_revision=activating.revision, profile=profile,
            compatibility=compatibility, registrations=registrations,
            operation_ref=operation_ref, actor=actor, now=now,
        )

    def begin_activation(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        operation_ref: str, actor: str, now: datetime,
        allowed: tuple[ModuleLifecycle, ...] = (ModuleLifecycle.STAGED,),
    ) -> ModuleLifecycleRecord:
        """Consume authority and durably enter ACTIVATING before dispatch."""
        self._validate_compatibility(package, profile, compatibility)
        self._validate_registrations(package, profile, registrations)
        self.capability_system.validate_batch(registrations)
        current = self.describe(package.manifest.module_id)
        if current is None or current.package_digest != package.package_digest:
            raise RuntimeError("verified package differs from lifecycle record")
        if current.lifecycle not in allowed:
            raise RuntimeError("module lifecycle cannot begin activation")
        self._authorize(
            operation="activate", current=current,
            expected_revision=expected_revision,
            target=ModuleLifecycle.ACTIVATING,
            operation_ref=operation_ref, actor=actor, now=now,
            profile=profile, package=package,
        )
        return self._transition(
            current.module_id, expected_revision=expected_revision,
            allowed=allowed, target=ModuleLifecycle.ACTIVATING,
            operation_ref=operation_ref, actor=actor,
            reason="authorized activation awaiting verified adapter start",
            now=now, active_profile=profile, authorized=False,
        )

    def complete_activation(
        self, package: VerifiedModulePackage, *, expected_revision: int,
        profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
        operation_ref: str, actor: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        """Register capabilities only after the caller verified adapter start."""
        self._validate_compatibility(package, profile, compatibility)
        self._validate_registrations(package, profile, registrations)
        current = self.describe(package.manifest.module_id)
        if current is None or current.package_digest != package.package_digest:
            raise RuntimeError("verified package differs from lifecycle record")
        if current.lifecycle is not ModuleLifecycle.ACTIVATING:
            raise RuntimeError("module is not awaiting activation completion")
        self.capability_system.register_batch(registrations)
        try:
            result = self._transition(
                current.module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.ACTIVATING,),
                target=ModuleLifecycle.ACTIVE, operation_ref=operation_ref,
                actor=actor,
                reason="verified adapter started; capabilities activated",
                now=now, active_profile=profile, authorized=False,
            )
        except BaseException:
            self.capability_system.unregister_batch(registrations)
            raise
        self._active_batches[current.module_id] = registrations
        return result

    def quarantine_uncertain_activation(
        self, module_id: str, *, expected_revision: int,
        operation_ref: str, reason: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        """Fail closed after an external activation cannot be reconciled.

        This transition can only reduce authority from ACTIVATING and never
        registers capabilities, so it is owned by Platform recovery rather
        than a fresh activation approval.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("recovery quarantine reason required")
        return self._transition(
            module_id, expected_revision=expected_revision,
            allowed=(ModuleLifecycle.ACTIVATING,),
            target=ModuleLifecycle.QUARANTINED,
            operation_ref=operation_ref, actor="platform:recovery",
            reason=reason, now=now, authorized=False,
        )

    @staticmethod
    def _validate_compatibility(
        package: VerifiedModulePackage, profile: OperationProfileKind,
        compatibility: ModuleCompatibilityReport,
    ) -> None:
        if not isinstance(compatibility, ModuleCompatibilityReport):
            raise TypeError("compatibility report required")
        if (
            compatibility.module_id != package.manifest.module_id
            or compatibility.version != package.manifest.version
            or compatibility.package_digest != package.package_digest
            or compatibility.profile is not profile
        ):
            raise PermissionError("compatibility report is for another package/profile")
        if not compatibility.compatible:
            raise PermissionError("module package is incompatible with target Platform")
        if not compatibility.authoritative:
            raise PermissionError("compatibility assessment is not authoritative")

    @staticmethod
    def _validate_registrations(
        package: VerifiedModulePackage, profile: OperationProfileKind,
        registrations: tuple[tuple[Capability, CapabilityHandler], ...],
    ) -> None:
        declared = {name for name, _ in package.manifest.capability_schemas}
        profile_contract = next(
            (item for item in package.manifest.profiles if item.profile_id is profile), None,
        )
        if profile_contract is None:
            raise ValueError("profile is not declared")
        names = {item.name for item, _ in registrations}
        if len(names) != len(registrations):
            raise ValueError("adapter capability registrations must be unique")
        if names != set(profile_contract.available_capability_ids) or not names.issubset(declared):
            raise PermissionError("adapter capabilities differ from signed profile")

    def resume(self, package: VerifiedModulePackage, *, expected_revision: int,
               profile: OperationProfileKind,
               compatibility: ModuleCompatibilityReport,
               registrations: tuple[tuple[Capability, CapabilityHandler], ...],
               operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        self._validate_compatibility(package, profile, compatibility)
        self._validate_registrations(package, profile, registrations)
        current = self.describe(package.manifest.module_id)
        if current is None or current.package_digest != package.package_digest:
            raise RuntimeError("verified package differs from lifecycle record")
        if current.lifecycle is not ModuleLifecycle.PAUSED:
            raise RuntimeError("only paused modules may resume")
        self._authorize(
            operation="resume", current=current,
            expected_revision=expected_revision, target=ModuleLifecycle.ACTIVE,
            operation_ref=operation_ref, actor=actor, now=now,
            profile=profile, package=package,
        )
        self.capability_system.register_batch(registrations)
        try:
            result = self._transition(
                current.module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.PAUSED,), target=ModuleLifecycle.ACTIVE,
                operation_ref=operation_ref, actor=actor,
                reason="reviewed adapter capabilities resumed", now=now,
                active_profile=profile, authorized=False,
            )
        except BaseException:
            self.capability_system.unregister_batch(registrations)
            raise
        self._active_batches[current.module_id] = registrations
        return result

    def pause(self, module_id: str, *, expected_revision: int,
              operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        batch = self._active_batches.get(module_id)
        if batch is None:
            raise RuntimeError("active adapter batch is unavailable")
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        self._authorize(
            operation="pause", current=current,
            expected_revision=expected_revision, target=ModuleLifecycle.PAUSED,
            operation_ref=operation_ref, actor=actor, now=now,
        )
        self.capability_system.unregister_batch(batch)
        try:
            result = self._transition(
                module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.ACTIVE,), target=ModuleLifecycle.PAUSED,
                operation_ref=operation_ref, actor=actor,
                reason="capabilities drained and paused", now=now,
                authorized=False,
            )
        except BaseException:
            self.capability_system.register_batch(batch)
            raise
        self._active_batches.pop(module_id, None)
        return result

    def begin_process_pause(
        self, module_id: str, *, expected_revision: int,
        operation_ref: str, actor: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        """Withdraw admissions and durably enter DRAINING before OS stop."""
        batch = self._active_batches.get(module_id)
        if batch is None:
            raise RuntimeError("active adapter batch is unavailable")
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        self._authorize(
            operation="pause", current=current,
            expected_revision=expected_revision, target=ModuleLifecycle.PAUSED,
            operation_ref=operation_ref, actor=actor, now=now,
        )
        self.capability_system.unregister_batch(batch)
        try:
            result = self._transition(
                module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.ACTIVE,), target=ModuleLifecycle.DRAINING,
                operation_ref=operation_ref, actor=actor,
                reason="capabilities withdrawn; process drain required", now=now,
                authorized=False,
            )
        except BaseException:
            self.capability_system.register_batch(batch)
            raise
        self._active_batches.pop(module_id, None)
        return result

    def complete_process_pause(
        self, module_id: str, *, expected_revision: int,
        operation_ref: str, now: datetime,
    ) -> ModuleLifecycleRecord:
        """Commit PAUSED only after Platform independently verified stop."""
        return self._transition(
            module_id, expected_revision=expected_revision,
            allowed=(ModuleLifecycle.DRAINING,), target=ModuleLifecycle.PAUSED,
            operation_ref=operation_ref, actor="platform:module-supervisor",
            reason="external process stop independently verified", now=now,
            authorized=False,
        )

    def disable(self, module_id: str, *, expected_revision: int,
                operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        if module_id in self._active_batches:
            raise RuntimeError("active module must be paused before disable")
        return self._transition(
            module_id, expected_revision=expected_revision,
            allowed=(ModuleLifecycle.STAGED, ModuleLifecycle.PAUSED,
                     ModuleLifecycle.QUARANTINED),
            target=ModuleLifecycle.INSTALLED_DISABLED,
            operation_ref=operation_ref, actor=actor,
            reason="module disabled; no capabilities registered", now=now,
            authorization_operation="disable",
        )

    def quarantine(self, module_id: str, *, expected_revision: int,
                   operation_ref: str, actor: str, reason: str,
                   now: datetime) -> ModuleLifecycleRecord:
        batch = self._active_batches.get(module_id)
        current = self.describe(module_id)
        if current is None:
            raise LookupError("unknown module")
        self._authorize(
            operation="quarantine", current=current,
            expected_revision=expected_revision,
            target=ModuleLifecycle.QUARANTINED,
            operation_ref=operation_ref, actor=actor, now=now,
        )
        if batch is not None:
            self.capability_system.unregister_batch(batch)
        try:
            result = self._transition(
                module_id, expected_revision=expected_revision,
                allowed=(ModuleLifecycle.ACTIVE, ModuleLifecycle.PAUSED,
                         ModuleLifecycle.STAGED,
                         ModuleLifecycle.INSTALLED_DISABLED),
                target=ModuleLifecycle.QUARANTINED,
                operation_ref=operation_ref, actor=actor,
                reason=reason or "module quarantined", now=now,
                authorized=False,
            )
        except BaseException:
            if batch is not None:
                self.capability_system.register_batch(batch)
            raise
        self._active_batches.pop(module_id, None)
        return result

    def update(self, package: VerifiedModulePackage, *, expected_revision: int,
               profile: OperationProfileKind,
               compatibility: ModuleCompatibilityReport,
               operation_ref: str, actor: str, now: datetime,
               _authorization_action: str = "updating") -> ModuleLifecycleRecord:
        """Switch a disabled package pointer; never activate the new adapter."""
        self._validate_compatibility(package, profile, compatibility)
        current = self.describe(package.manifest.module_id)
        if current is None:
            raise LookupError("unknown module")
        if current.package_digest == package.package_digest:
            raise ValueError("update package is identical to current package")
        if current.lifecycle not in {
            ModuleLifecycle.STAGED, ModuleLifecycle.PAUSED,
            ModuleLifecycle.INSTALLED_DISABLED, ModuleLifecycle.QUARANTINED,
        } or current.module_id in self._active_batches:
            raise RuntimeError("module must be inactive before update")
        if _authorization_action not in {"updating", "rolling_back"}:
            raise ValueError("unsupported package replacement action")
        operation = "rollback" if _authorization_action == "rolling_back" else "update"
        self._authorize(
            operation=operation, current=current,
            expected_revision=expected_revision, target=ModuleLifecycle.STAGED,
            operation_ref=operation_ref, actor=actor, now=now,
            profile=profile, package=package,
        )
        moment = now.astimezone(timezone.utc)
        destination, newly_created = self._store_package(package)
        try:
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT * FROM platform_module_lifecycle WHERE module_id=?",
                    (current.module_id,),
                ).fetchone()
                observed = self._record(row) if row is not None else None
                if observed is None or observed.revision != expected_revision or (
                    observed.package_digest != current.package_digest
                ):
                    raise RuntimeError("module lifecycle revision/state changed")
                db.execute(
                    "INSERT OR IGNORE INTO platform_module_release_history VALUES(?,?,?,?,?)",
                    (current.module_id, current.package_digest, current.version,
                     current.staged_path, moment.isoformat()),
                )
                revision = expected_revision + 1
                changed = db.execute(
                    """UPDATE platform_module_lifecycle SET version=?,package_digest=?,
                    lifecycle='staged',revision=?,active_profile=NULL,staged_path=?,
                    reason='verified update staged; activation pending',updated_at=?
                    WHERE module_id=? AND revision=?""",
                    (package.manifest.version, package.package_digest, revision,
                     str(destination), moment.isoformat(), current.module_id,
                     expected_revision),
                )
                if changed.rowcount != 1:
                    raise RuntimeError("module update compare-and-swap failed")
                db.execute(
                    "DELETE FROM platform_module_dependency WHERE module_id=?",
                    (current.module_id,),
                )
                db.executemany(
                    "INSERT INTO platform_module_dependency VALUES(?,?,?,?)",
                    tuple((current.module_id, item.module_id, item.minimum_version,
                           item.maximum_version_exclusive)
                          for item in package.manifest.dependencies),
                )
                db.execute(
                    "DELETE FROM platform_module_capability WHERE module_id=?",
                    (current.module_id,),
                )
                db.executemany(
                    "INSERT INTO platform_module_capability VALUES(?,?,?)",
                    tuple(
                        (current.module_id, capability_id, schema_ref)
                        for capability_id, schema_ref
                        in package.manifest.capability_schemas
                    ),
                )
                db.execute(
                    "INSERT INTO platform_module_policy VALUES(?,?,?,?) "
                    "ON CONFLICT(module_id) DO UPDATE SET "
                    "package_digest=excluded.package_digest,"
                    "placement_mode=excluded.placement_mode,"
                    "isolation_profile=excluded.isolation_profile",
                    (
                        current.module_id,
                        package.package_digest,
                        package.manifest.placement_mode.value,
                        package.manifest.isolation_profile,
                    ),
                )
                self._persist_manifest_projection(
                    db, package, replace_existing=True,
                )
                db.execute(
                    "INSERT INTO platform_module_lifecycle_event VALUES(NULL,?,?,?,?,?,?,?,?)",
                    (current.module_id, current.lifecycle.value,
                     ModuleLifecycle.STAGED.value, revision, operation_ref,
                     actor, "verified update staged; activation pending",
                     moment.isoformat()),
                )
        except BaseException:
            if newly_created:
                import shutil
                shutil.rmtree(destination, ignore_errors=True)
            raise
        return self.describe(current.module_id)  # type: ignore[return-value]

    def rollback(self, package: VerifiedModulePackage, *, expected_revision: int,
                 profile: OperationProfileKind,
                 compatibility: ModuleCompatibilityReport,
                 operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        """Restore an exact retained package as STAGED; activation remains separate."""
        self._validate_compatibility(package, profile, compatibility)
        current = self.describe(package.manifest.module_id)
        if current is None or current.module_id in self._active_batches:
            raise RuntimeError("inactive current module required for rollback")
        if current.lifecycle not in {
            ModuleLifecycle.STAGED, ModuleLifecycle.PAUSED,
            ModuleLifecycle.INSTALLED_DISABLED, ModuleLifecycle.QUARANTINED,
        }:
            raise RuntimeError("module lifecycle cannot rollback")
        with closing(self._connect()) as db:
            prior = db.execute(
                """SELECT 1 FROM platform_module_release_history
                WHERE module_id=? AND package_digest=? AND version=?""",
                (current.module_id, package.package_digest, package.manifest.version),
            ).fetchone()
        if prior is None:
            raise PermissionError("rollback target is not retained module history")
        # The update mechanism has the exact desired semantics: preserve the
        # current release as history and switch only the inactive staged pointer.
        return self.update(
            package, expected_revision=expected_revision, profile=profile,
            compatibility=compatibility, operation_ref=operation_ref,
            actor=actor, now=now, _authorization_action="rolling_back",
        )

    def remove(self, module_id: str, *, expected_revision: int,
               operation_ref: str, actor: str, now: datetime) -> ModuleLifecycleRecord:
        if module_id in self._active_batches:
            raise RuntimeError("active module must be paused before removal")
        with closing(self._connect()) as db:
            dependent = db.execute(
                """SELECT d.module_id FROM platform_module_dependency d
                JOIN platform_module_lifecycle l ON l.module_id=d.module_id
                WHERE d.dependency_id=? AND l.lifecycle NOT IN
                    ('discovered','validated','review_pending','removed')
                ORDER BY d.module_id LIMIT 1""",
                (module_id,),
            ).fetchone()
        if dependent is not None:
            raise RuntimeError(
                f"module is required by installed dependent {dependent[0]}"
            )
        # Package bytes are retained for audit/rollback. Physical deletion is a
        # separate reviewed retention operation, never an activation side effect.
        return self._transition(
            module_id, expected_revision=expected_revision,
            allowed=(ModuleLifecycle.INSTALLED_DISABLED,
                     ModuleLifecycle.QUARANTINED),
            target=ModuleLifecycle.REMOVED,
            operation_ref=operation_ref, actor=actor,
            reason="module removed from service; immutable evidence retained",
            now=now, authorization_operation="remove",
        )
