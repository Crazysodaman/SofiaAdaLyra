"""Non-mutating production baseline diagnostics for one Sofía instance.

The doctor is an operator observation tool. It never writes state, never
creates or migrates databases, and never grants authority. Every check
either observes existing material or reports explicitly that it is
UNKNOWN because nothing has been recorded yet.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import sqlite3
import sys

from sofia.platform.config.defaults import production_storage_layout
from sofia.platform.config.layout import RuntimeStorageLayout
from sofia.core.constitution.store import (
    ConstitutionIntegrityVerifier,
    ConstitutionStore,
)
from sofia.core.embodiment.store import EmbodimentStore
from sofia.core.identity.model import IdentityBootstrapMode
from sofia.core.identity.store import IdentityStore
from sofia.core.personality.store import PersonalityStore
from sofia.platform.run.process_lock import StateProcessLock
from sofia.platform.state.canonical_sqlite import (
    CanonicalSQLiteGuard,
    require_existing_sqlite,
)
from sofia.platform.state.component_schema import PRODUCTION_COMPONENT_SCHEMAS

STATUS_OK = "OK"
STATUS_DEGRADED = "DEGRADED"
STATUS_FAILED = "FAILED"
STATUS_UNKNOWN = "UNKNOWN"
_STATUSES = frozenset(
    {STATUS_OK, STATUS_DEGRADED, STATUS_FAILED, STATUS_UNKNOWN}
)

_LOCK_RESOURCES = ("tray", "discord")


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """One individually observed baseline check outcome."""

    id: str
    title: str
    status: str
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("check id must be nonempty")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("check title must be nonempty")
        if self.status not in _STATUSES:
            raise ValueError("unknown doctor check status")
        if not isinstance(self.detail, str):
            raise TypeError("check detail must be text")

    @property
    def failed(self) -> bool:
        return self.status == STATUS_FAILED

    @property
    def degraded(self) -> bool:
        return self.status == STATUS_DEGRADED


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Ordered baseline check outcomes plus summary counts."""

    generated_at: datetime
    state_path: Path
    checks: tuple[DoctorCheck, ...]
    _counts: dict[str, int] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime):
            raise TypeError("generated_at must be a datetime")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.state_path, Path):
            raise TypeError("state_path must be a Path")
        if not isinstance(self.checks, tuple):
            raise TypeError("checks must be a tuple of DoctorCheck")
        for check in self.checks:
            if not isinstance(check, DoctorCheck):
                raise TypeError("checks must contain only DoctorCheck items")
        counts = {status: 0 for status in _STATUSES}
        for check in self.checks:
            counts[check.status] += 1
        object.__setattr__(self, "_counts", counts)

    @property
    def outcome(self) -> str:
        if self.failed_count:
            return "failed"
        if self.degraded_count:
            return "degraded"
        return "healthy"

    @property
    def failed_count(self) -> int:
        return self._counts[STATUS_FAILED]

    @property
    def degraded_count(self) -> int:
        return self._counts[STATUS_DEGRADED]

    @property
    def unknown_count(self) -> int:
        return self._counts[STATUS_UNKNOWN]

    @property
    def ok_count(self) -> int:
        return self._counts[STATUS_OK]

    def check(self, check_id: str) -> DoctorCheck | None:
        for check in self.checks:
            if check.id == check_id:
                return check
        return None

    def render_text(self) -> str:
        lines = [
            f"Sofía baseline doctor — {self.outcome.upper()} "
            f"(OK={self.ok_count} DEGRADED={self.degraded_count} "
            f"FAILED={self.failed_count} UNKNOWN={self.unknown_count})",
            f"generated_at: {self.generated_at.isoformat()}",
            f"state_path:   {self.state_path}",
        ]
        for check in self.checks:
            lines.append(
                f"[{check.status:<8}] {check.id}: {check.title} — {check.detail}"
            )
        return "\n".join(lines)


def _check_result(
    check_id: str,
    title: str,
    check,
) -> DoctorCheck:
    try:
        return check()
    except Exception as exc:  # noqa: BLE001 doctor never raises a check
        return DoctorCheck(
            id=check_id,
            title=title,
            status=STATUS_FAILED,
            detail=f"{type(exc).__name__}: {exc}",
        )


def _storage_check(layout: RuntimeStorageLayout) -> DoctorCheck:
    require_existing = (
        layout.identity_bootstrap_mode is IdentityBootstrapMode.REQUIRE_EXISTING
    )
    entries = (
        ("constitution.md", layout.constitution_path, True),
        ("constitution.sha256", layout.constitution_hash_path, True),
        ("personality.json", layout.personality_path, True),
        ("avatar.json", layout.avatar_path, True),
        (
            "identity.json",
            layout.identity_path,
            require_existing,
        ),
    )
    missing_required: list[str] = []
    missing_optional: list[str] = []
    for name, path, required in entries:
        if path.exists():
            continue
        if required:
            missing_required.append(name)
        elif name == "identity.json":
            missing_optional.append(name)
    if missing_required:
        return DoctorCheck(
            id="storage_layout",
            title="canonical storage layout",
            status=STATUS_FAILED,
            detail="missing required authority/state files: "
            + ", ".join(missing_required),
        )
    detail = (
        f"state_root={layout.state_root}; all required files present"
    )
    if missing_optional:
        detail += (
            f"; identity not bootstrapped yet ({missing_optional[0]} will be "
            "created by the first authorized start)"
        )
    return DoctorCheck(
        id="storage_layout",
        title="canonical storage layout",
        status=STATUS_OK,
        detail=detail,
    )


def _canonical_state_check(state_path: Path) -> DoctorCheck:
    resolved, identity = require_existing_sqlite(state_path)
    size = resolved.stat(follow_symlinks=False).st_size
    return DoctorCheck(
        id="canonical_state",
        title="canonical SQLite state",
        status=STATUS_OK,
        detail=(
            f"pinned canonical file {resolved} "
            f"(dev={identity[0]}, ino={identity[1]}, size={size} bytes)"
        ),
    )


def _integrity_check(state_path: Path) -> DoctorCheck:
    guard = CanonicalSQLiteGuard(state_path)
    with closing(guard.connect(timeout=10, read_only=True)) as db:
        rows = db.execute("PRAGMA quick_check").fetchall()
    values = tuple(str(row[0]) for row in rows)
    if not values:
        raise sqlite3.DatabaseError("quick_check returned no rows")
    if any(value != "ok" for value in values):
        return DoctorCheck(
            id="sqlite_integrity",
            title="canonical SQLite integrity",
            status=STATUS_FAILED,
            detail="quick_check reported: " + "; ".join(values[:8]),
        )
    with closing(guard.connect(timeout=10, read_only=True)) as db:
        journal = db.execute("PRAGMA journal_mode").fetchone()[0]
    return DoctorCheck(
        id="sqlite_integrity",
        title="canonical SQLite integrity",
        status=STATUS_OK,
        detail=f"quick_check ok (journal_mode={journal})",
    )


def _schema_registry_check(state_path: Path) -> DoctorCheck:
    guard = CanonicalSQLiteGuard(state_path)
    with closing(guard.connect(timeout=10, read_only=True)) as db:
        registered = db.execute(
            "PRAGMA table_info(state_schema_component)"
        ).fetchall()
        if not registered:
            return DoctorCheck(
                id="schema_registry",
                title="production schema registry",
                status=STATUS_UNKNOWN,
                detail=(
                    "state_schema_component not registered yet; startup "
                    "registration is part of the first application start"
                ),
            )
        rows = db.execute(
            "SELECT component, current_revision, readable_min, readable_max,"
            " writable_min, writable_max FROM state_schema_component"
        ).fetchall()
    stored = {
        str(row[0]): tuple(int(value) for value in row[1:])
        for row in rows
    }
    mismatches = []
    unresolved = []
    for schema in PRODUCTION_COMPONENT_SCHEMAS:
        expected = (
            schema.compatibility.current_revision,
            schema.compatibility.readable_min,
            schema.compatibility.readable_max,
            schema.compatibility.writable_min,
            schema.compatibility.writable_max,
        )
        actual = stored.get(schema.component)
        if actual is None:
            unresolved.append(schema.component)
        elif actual != expected:
            mismatches.append(
                f"{schema.component}: registered={actual} expected={expected}"
            )
    if mismatches:
        return DoctorCheck(
            id="schema_registry",
            title="production schema registry",
            status=STATUS_FAILED,
            detail="registry disagrees with reviewed schemas: "
            + "; ".join(mismatches),
        )
    detail = f"{len(stored)} components registered and compatible"
    if unresolved:
        detail += f"; {len(unresolved)} expected components not yet registered"
    return DoctorCheck(
        id="schema_registry",
        title="production schema registry",
        status=STATUS_OK,
        detail=detail,
    )


def _constitution_check(
    constitution_path: Path,
    hash_path: Path,
) -> DoctorCheck:
    store = ConstitutionStore(constitution_path)
    constitution = store.load()
    ConstitutionIntegrityVerifier(hash_path).verify(constitution)
    return DoctorCheck(
        id="constitution_integrity",
        title="constitution integrity",
        status=STATUS_OK,
        detail=(
            f"version={constitution.version} "
            f"sha256={constitution.content_hash[:16]}\u2026"
        ),
    )


def _identity_check(
    identity_path: Path,
    bootstrap_mode: IdentityBootstrapMode,
) -> DoctorCheck:
    if not identity_path.exists():
        if bootstrap_mode is IdentityBootstrapMode.REQUIRE_EXISTING:
            raise FileNotFoundError(identity_path)
        return DoctorCheck(
            id="identity_authenticity",
            title="institutional identity",
            status=STATUS_UNKNOWN,
            detail=(
                "identity not bootstrapped yet; the first authorized "
                "start creates it"
            ),
        )
    identity = IdentityStore(
        identity_path,
        bootstrap_mode=IdentityBootstrapMode.REQUIRE_EXISTING,
    ).load()
    return DoctorCheck(
        id="identity_authenticity",
        title="institutional identity",
        status=STATUS_OK,
        detail=f"name={identity.name} instance_id={identity.instance_id}",
    )


def _personality_check(personality_path: Path) -> DoctorCheck:
    profile = PersonalityStore(personality_path).load()
    return DoctorCheck(
        id="personality_loadability",
        title="personality definition",
        status=STATUS_OK,
        detail=f"profile loaded ({len(profile.traits)} traits)",
    )


def _embodiment_check(avatar_path: Path) -> DoctorCheck:
    avatar = EmbodimentStore(avatar_path).load()
    name = getattr(avatar, "name", None)
    detail = "avatar definition loaded"
    if name:
        detail += f" (name={name})"
    return DoctorCheck(
        id="embodiment_loadability",
        title="embodiment definition",
        status=STATUS_OK,
        detail=detail,
    )


def _heartbeat_check(state_path: Path) -> DoctorCheck:
    guard = CanonicalSQLiteGuard(state_path)
    with closing(guard.connect(timeout=10, read_only=True)) as db:
        present = db.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name='run_application_heartbeat'"
        ).fetchall()
        if not present:
            return DoctorCheck(
                id="startup_heartbeat",
                title="startup readiness heartbeat",
                status=STATUS_UNKNOWN,
                detail=(
                    "no application heartbeat recorded yet; the runtime "
                    "records readiness on the first supervised start"
                ),
            )
        row = db.execute(
            """
            SELECT instance_id, recorded_at, ready, runtime_state,
                   database_writable, background_running, detail
            FROM run_application_heartbeat
            ORDER BY recorded_at DESC
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return DoctorCheck(
            id="startup_heartbeat",
            title="startup readiness heartbeat",
            status=STATUS_UNKNOWN,
            detail="heartbeat table exists but no heartbeat recorded",
        )
    try:
        recorded_at = datetime.fromisoformat(str(row[1]))
    except ValueError as exc:
        return DoctorCheck(
            id="startup_heartbeat",
            title="startup readiness heartbeat",
            status=STATUS_UNKNOWN,
            detail=f"unparseable heartbeat timestamp: {exc}",
        )
    ready = bool(row[2])
    details = (
        f"instance={row[0]} recorded_at={row[1]} ready={ready} "
        f"runtime_state={row[3]} database_writable={bool(row[4])} "
        f"background_running={bool(row[5])} detail={row[6]!r}"
    )
    if not ready:
        return DoctorCheck(
            id="startup_heartbeat",
            title="startup readiness heartbeat",
            status=STATUS_DEGRADED,
            detail=details,
        )
    return DoctorCheck(
        id="startup_heartbeat",
        title="startup readiness heartbeat",
        status=STATUS_OK,
        detail=f"last ready heartbeat {recorded_at.isoformat()}: {row[3]}",
    )


def _lock_file_check(state_path: Path) -> DoctorCheck:
    observations = []
    for resource in _LOCK_RESOURCES:
        lock = StateProcessLock(state_path, resource=resource)
        observations.append(
            f"{resource}: lock_file_present={lock.path.exists()}"
        )
    return DoctorCheck(
        id="writer_lock_files",
        title="companion writer lock files",
        status=STATUS_OK,
        detail=(
            "; ".join(observations)
            + " (occupancy cannot be verified read-only; presence is the "
            "observed fact)"
        ),
    )


def run_doctor(
    *,
    state_path: Path | str | None = None,
) -> DoctorReport:
    """Observe the full non-mutating baseline for one canonical instance."""
    if state_path is None:
        layout = production_storage_layout()
    else:
        state_path = Path(state_path)
        layout = production_storage_layout(state_path=state_path)

    canonical = layout.state_path
    checks = [
        _check_result(
            "storage_layout",
            "canonical storage layout",
            lambda: _storage_check(layout),
        ),
        _check_result(
            "canonical_state",
            "canonical SQLite state",
            lambda: _canonical_state_check(canonical),
        ),
        _check_result(
            "sqlite_integrity",
            "canonical SQLite integrity",
            lambda: _integrity_check(canonical),
        ),
        _check_result(
            "schema_registry",
            "production schema registry",
            lambda: _schema_registry_check(canonical),
        ),
        _check_result(
            "constitution_integrity",
            "constitution integrity",
            lambda: _constitution_check(
                layout.constitution_path,
                layout.constitution_hash_path,
            ),
        ),
        _check_result(
            "identity_authenticity",
            "institutional identity",
            lambda: _identity_check(
                layout.identity_path,
                layout.identity_bootstrap_mode,
            ),
        ),
        _check_result(
            "personality_loadability",
            "personality definition",
            lambda: _personality_check(layout.personality_path),
        ),
        _check_result(
            "embodiment_loadability",
            "embodiment definition",
            lambda: _embodiment_check(layout.avatar_path),
        ),
        _check_result(
            "startup_heartbeat",
            "startup readiness heartbeat",
            lambda: _heartbeat_check(canonical),
        ),
        _check_result(
            "writer_lock_files",
            "companion writer lock files",
            lambda: _lock_file_check(canonical),
        ),
    ]
    return DoctorReport(
        generated_at=datetime.now(timezone.utc),
        state_path=canonical,
        checks=tuple(checks),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.platform.run.doctor",
        description=(
            "Non-mutating production baseline diagnostics for Sofía."
        ),
    )
    parser.add_argument(
        "--state-path",
        help="explicit canonical state directory/state database path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON report",
    )
    args = parser.parse_args(argv)

    resolution = None
    if args.state_path:
        candidate = Path(args.state_path)
        if candidate.suffix == ".db":
            resolution = candidate
        else:
            resolution = candidate / "sofia.db"

    try:
        report = run_doctor(state_path=resolution)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"doctor refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001 unexplained failure is upstream
        print(
            f"doctor refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    if args.json:
        payload = {
            "generated_at": report.generated_at.isoformat(),
            "state_path": str(report.state_path),
            "outcome": report.outcome,
            "checks": [
                {
                    "id": check.id,
                    "title": check.title,
                    "status": check.status,
                    "detail": check.detail,
                }
                for check in report.checks
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(report.render_text())

    if report.outcome == "failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
