"""Canonical Sofía module registry: trust states, compatibility, health.

The registry persists validated manifests with typed trust states.
Verification is an owner-session action. Discovered candidates are only
ever recorded as candidates; they never become trusted through any
automatic path. Module health is a projection over authorized codebase
inspection evidence plus the verified registry, never an inference
granted by mere existence of files.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import sqlite3

from sofia.codebase.model import CodebaseInspectionEvidence
from sofia.modules.manifest import ModuleManifest, parse_manifest
from sofia.social.model import PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class TrustState(str, Enum):
    CANDIDATE = "candidate"
    VERIFIED = "verified"
    RETIRED = "retired"


class ModuleHealth(str, Enum):
    UNKNOWN = "unknown"
    OBSERVED = "observed"
    DEGRADED = "degraded"
    SUSPECT = "suspect"


class ModuleRegistryError(RuntimeError):
    """Registry race, cycle, or stale-revision condition."""


def _aware_utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("registry timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ModuleRegistration:
    """One persisted revision of a module manifest with its trust state."""

    manifest: ModuleManifest
    revision: int
    trust_state: TrustState
    recorded_at: datetime
    source_path: str

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("registration revision must be a positive int")
        if not isinstance(self.trust_state, TrustState):
            raise TypeError("trust_state must be a TrustState")
        if not isinstance(self.manifest, ModuleManifest):
            raise TypeError("manifest must be a ModuleManifest")
        if not isinstance(self.source_path, str):
            raise ValueError("source_path must be text")
        if self.trust_state is TrustState.CANDIDATE:
            if not self.source_path:
                raise ValueError(
                    "candidate registrations must carry their observed source"
                    " path"
                )
        elif self.source_path:
            raise ValueError(
                "verified and retired registrations drop the source path"
            )
        if _aware_utc(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


@dataclass(frozen=True, slots=True)
class ModuleHealthReport:
    name: str
    manifest_version: str
    trust_state: TrustState
    health: ModuleHealth
    detail: str


@dataclass(frozen=True, slots=True)
class HealthChange:
    name: str
    previous: ModuleHealth
    current: ModuleHealth


class ModuleRegistryStore:
    """Canonical persistence for module manifests and health cache."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS modules_manifest_revision (
                    manifest_name TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    manifest_version TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    trust_state TEXT NOT NULL CHECK(trust_state IN (
                        'candidate','verified','retired')),
                    source_path TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(manifest_name,revision)
                );
                CREATE TABLE IF NOT EXISTS modules_manifest_current (
                    manifest_name TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS modules_health_cache (
                    manifest_name TEXT PRIMARY KEY,
                    health TEXT NOT NULL CHECK(health IN (
                        'unknown','observed','degraded','suspect')),
                    inspection_digest TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode_value(registration: ModuleRegistration) -> dict:
        m = registration.manifest
        return {
            "name": m.name,
            "version": m.version,
            "purpose": m.purpose,
            "boundary_notes": m.boundary_notes,
            "declared_capabilities": list(m.declared_capabilities),
            "declared_dependencies": list(m.declared_dependencies),
            "authority_boundary": m.authority_boundary,
        }

    @staticmethod
    def _decode_value(row: sqlite3.Row) -> ModuleRegistration:
        document = json.loads(row["document_json"])
        return ModuleRegistration(
            manifest=parse_manifest(document),
            revision=int(row["revision"]),
            trust_state=TrustState(row["trust_state"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
            source_path=row["source_path"],
        )

    def persist(
        self, registration: ModuleRegistration, *, expected_revision: int | None,
    ) -> ModuleRegistration:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT manifest_name,revision FROM modules_manifest_current
                WHERE manifest_name=?""",
                (registration.manifest.name,),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise ModuleRegistryError(
                        "manifest already registered; revise it instead"
                    )
                if registration.revision != 1:
                    raise ModuleRegistryError(
                        "first registration requires revision 1"
                    )
            else:
                if (
                    row is None
                    or int(row["revision"]) != expected_revision
                ):
                    raise ModuleRegistryError(
                        "revision changed or manifest is absent; reload first"
                    )
            db.execute(
                """INSERT INTO modules_manifest_revision VALUES(?,?,?,?,?,?,?)""",
                (
                    registration.manifest.name,
                    registration.revision,
                    registration.manifest.version,
                    json.dumps(
                        self._encode_value(registration), sort_keys=True
                    ),
                    registration.trust_state.value,
                    registration.source_path,
                    registration.recorded_at.isoformat(),
                ),
            )
            if row is None:
                db.execute(
                    """INSERT INTO modules_manifest_current
                    (manifest_name,revision) VALUES(?,?)""",
                    (registration.manifest.name, registration.revision),
                )
            else:
                db.execute(
                    """UPDATE modules_manifest_current SET revision=?
                    WHERE manifest_name=?""",
                    (registration.revision, registration.manifest.name),
                )
        return registration

    def current(self, name: str) -> ModuleRegistration | None:
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM modules_manifest_current c
                JOIN modules_manifest_revision r
                ON r.manifest_name=c.manifest_name
                AND r.revision=c.revision
                WHERE c.manifest_name=?""",
                (name,),
            ).fetchone()
        return None if row is None else self._decode_value(row)

    def all_current(self) -> tuple[ModuleRegistration, ...]:
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM modules_manifest_current c
                JOIN modules_manifest_revision r
                ON r.manifest_name=c.manifest_name
                AND r.revision=c.revision
                ORDER BY c.manifest_name"""
            ).fetchall()
        return tuple(self._decode_value(row) for row in rows)

    def set_cache(
        self,
        *,
        name: str,
        health: ModuleHealth,
        inspection_digest: str,
        observed_at: datetime,
    ) -> None:
        _aware_utc(observed_at)
        with closing(self._open()) as db, db:
            db.execute(
                """INSERT INTO modules_health_cache
                (manifest_name,health,inspection_digest,observed_at)
                VALUES(?,?,?,?)
                ON CONFLICT(manifest_name) DO UPDATE SET
                health=excluded.health,
                inspection_digest=excluded.inspection_digest,
                observed_at=excluded.observed_at""",
                (
                    name,
                    health.value,
                    inspection_digest,
                    observed_at.isoformat(),
                ),
            )

    def cached(self) -> dict[str, tuple[ModuleHealth, str]]:
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT manifest_name,health,inspection_digest
                FROM modules_health_cache"""
            ).fetchall()
        return {
            row["manifest_name"]: (
                ModuleHealth(row["health"]),
                row["inspection_digest"],
            )
            for row in rows
        }


def _active_dependency_edges(
    registrations: tuple[ModuleRegistration, ...],
    *,
    extra_name: str | None = None,
    extra_deps: tuple[str, ...] = (),
) -> dict[str, frozenset[str]]:
    edges: dict[str, frozenset[str]] = {}
    names = {
        registration.manifest.name
        for registration in registrations
        if registration.trust_state in (TrustState.CANDIDATE, TrustState.VERIFIED)
    }
    if extra_name is not None:
        names = names | {extra_name}
    for registration in registrations:
        if registration.trust_state not in (
            TrustState.CANDIDATE, TrustState.VERIFIED,
        ):
            continue
        deps = frozenset(
            dependency
            for dependency in registration.manifest.declared_dependencies
            if dependency in names
        )
        edges[registration.manifest.name] = deps
    if extra_name is not None:
        edges[extra_name] = frozenset(
            dependency
            for dependency in extra_deps
            if dependency in names or dependency == extra_name
        )
    return edges


def _has_dependency_cycle(edges: dict[str, frozenset[str]]) -> bool:
    resolved = {
        node: frozenset(dep for dep in deps if dep in edges)
        for node, deps in edges.items()
    }
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in resolved}

    def visit(node: str) -> bool:
        color[node] = GRAY
        for dependency in resolved[node]:
            if color[dependency] == GRAY:
                return True
            if color[dependency] == WHITE and visit(dependency):
                return True
        color[node] = BLACK
        return False

    return any(
        color[node] == WHITE and visit(node) for node in resolved
    )


class ModuleRegistryService:
    """Owner-session-gated registry with compatibility and health views."""

    def __init__(self, store: ModuleRegistryStore) -> None:
        self._store = store

    @property
    def store(self) -> ModuleRegistryStore:
        return self._store

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "module registry writes require the authenticated owner"
            )

    def record_candidate(
        self,
        principal: PrincipalContext,
        *,
        manifest: ModuleManifest,
        source_path: str,
        recorded_at: datetime | None = None,
    ) -> ModuleRegistration:
        self._require_sparks(principal)
        stamp = _aware_utc(recorded_at) if recorded_at is not None else _aware_utc(
            datetime.now(timezone.utc)
        )
        edges = _active_dependency_edges(
            self._store.all_current(),
            extra_name=manifest.name,
            extra_deps=manifest.declared_dependencies,
        )
        if _has_dependency_cycle(edges):
            raise ModuleRegistryError(
                "dependency cycle detected; registration refused"
            )
        registration = ModuleRegistration(
            manifest=manifest,
            revision=1,
            trust_state=TrustState.CANDIDATE,
            recorded_at=stamp,
            source_path=source_path,
        )
        return self._store.persist(registration, expected_revision=None)

    def verify(
        self,
        principal: PrincipalContext,
        *,
        name: str,
        expected_revision: int,
        inspection: CodebaseInspectionEvidence,
        recorded_at: datetime | None = None,
    ) -> ModuleRegistration:
        """Promote a candidate to verified, re-checking hard conditions."""
        self._require_sparks(principal)
        current = self._store.current(name)
        if current is None:
            raise LookupError("unknown module manifest")
        if current.revision != expected_revision:
            raise ModuleRegistryError("revision changed; reload before verify")
        if current.trust_state is not TrustState.CANDIDATE:
            raise ModuleRegistryError(
                "only candidate manifests can be verified"
            )
        self._require_code_observation(name, inspection)
        edges = _active_dependency_edges(
            self._store.all_current(),
        )
        if _has_dependency_cycle(edges):
            raise ModuleRegistryError("dependency cycle detected")
        stamp = _aware_utc(recorded_at) if recorded_at is not None else _aware_utc(
            datetime.now(timezone.utc)
        )
        registration = ModuleRegistration(
            manifest=current.manifest,
            revision=expected_revision + 1,
            trust_state=TrustState.VERIFIED,
            recorded_at=stamp,
            source_path="",
        )
        return self._store.persist(
            registration, expected_revision=expected_revision,
        )

    def retire(
        self,
        principal: PrincipalContext,
        *,
        name: str,
        expected_revision: int,
        recorded_at: datetime | None = None,
    ) -> ModuleRegistration:
        self._require_sparks(principal)
        current = self._store.current(name)
        if current is None:
            raise LookupError("unknown module manifest")
        if current.revision != expected_revision:
            raise ModuleRegistryError("revision changed; reload before retire")
        stamp = _aware_utc(recorded_at) if recorded_at is not None else _aware_utc(
            datetime.now(timezone.utc)
        )
        registration = ModuleRegistration(
            manifest=current.manifest,
            revision=expected_revision + 1,
            trust_state=TrustState.RETIRED,
            recorded_at=stamp,
            source_path="",
        )
        return self._store.persist(
            registration, expected_revision=expected_revision,
        )

    @staticmethod
    def _require_code_observation(
        name: str, inspection: CodebaseInspectionEvidence,
    ) -> None:
        if not inspection.python_modules:
            raise ModuleRegistryError(
                f"cannot verify {name}: no code observation available"
            )
        if not any(
            python_module.module_name.startswith(name)
            for python_module in inspection.python_modules
        ):
            raise ModuleRegistryError(
                f"cannot verify {name}: implementation not observed in the "
                "authorized inspection evidence"
            )

    @staticmethod
    def _check_cycles(
        registrations: tuple[ModuleRegistration, ...], name: str,
        _visited: list[str],
    ) -> bool:
        """Detect dependency cycles among currently registered manifests."""
        graph = {
            reg.manifest.name: {
                dep
                for dep in reg.manifest.declared_dependencies
                if any(other.manifest.name == dep for other in registrations)
            }
            for reg in registrations
        }
        graph[name] = set(
            next(
                (
                    reg.manifest.declared_dependencies
                    for reg in registrations
                    if reg.manifest.name == name
                ),
                set(),
            )
        )
        for start in graph:
            stack: list[str] = []
            visiting: set[str] = set()
            node: str | None = start
            while node is not None:
                if node in visiting:
                    if node == start:
                        return False
                    break
                stack.append(node)
                visiting.add(node)
                deps = [
                    dep
                    for dep in graph.get(node, ())
                    if any(
                        registration.manifest.name == dep
                        for registration in registrations
                    )
                    or dep == name
                ]
                node = next(iter(deps), None) if deps else None
        return True

    @staticmethod
    def compatibility(
        manifest: ModuleManifest,
        registrations: tuple[ModuleRegistration, ...],
    ) -> tuple[tuple[str, str], ...]:
        """Typed compatibility entries: (dependency, assessment)."""
        by_name = {reg.manifest.name: reg for reg in registrations}
        entries: list[tuple[str, str]] = []
        for dependency in manifest.declared_dependencies:
            other = by_name.get(dependency)
            if other is None:
                entries.append((dependency, "unregistered"))
            elif other.trust_state is not TrustState.VERIFIED:
                entries.append((dependency, "candidate-only"))
            elif (
                other.manifest.version_parts[0]
                != manifest.version_parts[0]
            ):
                entries.append((dependency, "major-version-mismatch"))
            else:
                entries.append((dependency, "compatible"))
        return tuple(entries)

    def compatibility_report(
        self, name: str,
    ) -> tuple[tuple[str, str], ...]:
        registration = self._store.current(name)
        if registration is None:
            raise LookupError("unknown module manifest")
        return self.compatibility(registration.manifest, self._store.all_current())

    def health_projection(
        self, inspection: CodebaseInspectionEvidence,
    ) -> tuple[ModuleHealthReport, ...]:
        reports: list[ModuleHealthReport] = []
        for registration in self._store.all_current():
            manifest = registration.manifest
            matches = tuple(
                python_module
                for python_module in inspection.python_modules
                if python_module.module_name.startswith(manifest.name)
            )
            if registration.trust_state is not TrustState.VERIFIED:
                health = ModuleHealth.UNKNOWN
                detail = f"trust_state={registration.trust_state.value}"
            elif not matches:
                health = ModuleHealth.SUSPECT
                detail = "implementation absent from authorized inspection"
            elif any(
                python_module.parse_error for python_module in matches
            ):
                health = ModuleHealth.DEGRADED
                detail = "parse errors observed in matching modules"
            else:
                health = ModuleHealth.OBSERVED
                detail = f"{len(matches)} matching modules observed"
            reports.append(
                ModuleHealthReport(
                    name=manifest.name,
                    manifest_version=manifest.version,
                    trust_state=registration.trust_state,
                    health=health,
                    detail=detail,
                )
            )
        return tuple(reports)

    def correlate_health(
        self,
        *,
        inspection: CodebaseInspectionEvidence,
        inspection_digest: str,
        now: datetime | None = None,
    ) -> tuple[HealthChange, ...]:
        """Persist the health cache and report changes since last see."""
        if not isinstance(inspection_digest, str) or len(
            inspection_digest
        ) not in (64,):
            raise ValueError("inspection_digest must be a 64-hex digest")
        stamp = _aware_utc(now) if now is not None else _aware_utc(
            datetime.now(timezone.utc)
        )
        previous = dict(self._store.cached())
        changes: list[HealthChange] = []
        for report in self.health_projection(inspection):
            old_health, _old_digest = previous.get(
                report.name, (ModuleHealth.UNKNOWN, "")
            )
            self._store.set_cache(
                name=report.name,
                health=report.health,
                inspection_digest=inspection_digest,
                observed_at=stamp,
            )
            if report.health is not old_health:
                changes.append(
                    HealthChange(
                        name=report.name,
                        previous=old_health,
                        current=report.health,
                    )
                )
        return tuple(changes)
