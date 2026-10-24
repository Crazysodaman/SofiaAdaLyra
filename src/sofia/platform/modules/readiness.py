"""Independent evidence projection for module release readiness."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
import sqlite3

from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

from .lifecycle import ModuleLifecycle, ModuleLifecycleRecord
from .package import SignedModuleManifest


_SHA = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
_EVIDENCE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}$")


class PlatformReadiness(str, Enum):
    DESIGN = "design"
    ALPHA = "alpha"
    BETA = "beta"
    RELEASE_CANDIDATE = "release_candidate"
    PRODUCTION_READY = "production_ready"
    BLOCKED = "blocked"


class ReadinessEvidenceKind(str, Enum):
    TEST = "test"
    SECURITY_AUDIT = "security_audit"
    INDEPENDENT_REVIEW = "independent_review"
    COMPATIBILITY = "compatibility"
    INTEROPERABILITY = "interoperability"
    ROLLBACK = "rollback"
    MATCHING_CI = "matching_ci"
    HOST_ACCEPTANCE = "host_acceptance"


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    evidence_id: str
    module_id: str
    package_digest: str
    source_sha: str
    kind: ReadinessEvidenceKind
    issuer: str
    passed: bool
    observed_at: datetime
    detail_ref: str
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    def __post_init__(self) -> None:
        for value, label in ((self.evidence_id, "evidence_id"),
                             (self.module_id, "module_id"),
                             (self.issuer, "issuer"),
                             (self.detail_ref, "detail_ref")):
            if not isinstance(value, str) or _EVIDENCE_ID.fullmatch(value) is None:
                raise ValueError(f"invalid {label}")
        if not isinstance(self.package_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.package_digest
        ):
            raise ValueError("package_digest must be SHA-256")
        if not isinstance(self.source_sha, str) or _SHA.fullmatch(self.source_sha) is None:
            raise ValueError("source_sha must be exact Git/SHA-256 digest")
        if not isinstance(self.kind, ReadinessEvidenceKind):
            raise TypeError("kind must be ReadinessEvidenceKind")
        if type(self.passed) is not bool:
            raise TypeError("passed must be bool")
        if self.issuer in {self.module_id, f"module:{self.module_id}"}:
            raise PermissionError("module cannot certify itself")
        for value in (self.observed_at, self.revoked_at):
            if value is not None and (
                not isinstance(value, datetime) or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError("evidence timestamps must be timezone-aware")
        if (self.revoked_at is None) != (self.revocation_reason is None):
            raise ValueError("revocation time and reason must appear together")


@dataclass(frozen=True, slots=True)
class ModuleReadinessReport:
    module_id: str
    source_sha: str
    status: PlatformReadiness
    satisfied: tuple[ReadinessEvidenceKind, ...]
    missing: tuple[ReadinessEvidenceKind, ...]
    reasons: tuple[str, ...]
    health_is_not_readiness: bool = True
    activation_authorized: bool = False


class ReadinessEvidenceStore:
    def __init__(
        self, state_path: Path, *, trusted_issuers: frozenset[str],
    ) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be Path")
        if not isinstance(trusted_issuers, frozenset) or not trusted_issuers or any(
            not isinstance(item, str) or _EVIDENCE_ID.fullmatch(item) is None
            for item in trusted_issuers
        ):
            raise ValueError("trusted readiness issuers must be explicit identifiers")
        self._trusted_issuers = trusted_issuers
        self._guard = CanonicalSQLiteGuard(state_path)
        with closing(self._connect()) as db, db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS platform_module_readiness_evidence(
                evidence_id TEXT PRIMARY KEY,module_id TEXT NOT NULL,
                package_digest TEXT NOT NULL,source_sha TEXT NOT NULL,
                kind TEXT NOT NULL,issuer TEXT NOT NULL,passed INTEGER NOT NULL,
                observed_at TEXT NOT NULL,detail_ref TEXT NOT NULL,
                revoked_at TEXT,revocation_reason TEXT)"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _record(row: sqlite3.Row) -> ReadinessEvidence:
        return ReadinessEvidence(
            row["evidence_id"], row["module_id"], row["package_digest"],
            row["source_sha"], ReadinessEvidenceKind(row["kind"]), row["issuer"],
            bool(row["passed"]), datetime.fromisoformat(row["observed_at"]),
            row["detail_ref"],
            None if row["revoked_at"] is None else datetime.fromisoformat(row["revoked_at"]),
            row["revocation_reason"],
        )

    def record(self, evidence: ReadinessEvidence) -> ReadinessEvidence:
        if not isinstance(evidence, ReadinessEvidence):
            raise TypeError("evidence must be ReadinessEvidence")
        if evidence.issuer not in self._trusted_issuers:
            raise PermissionError("readiness evidence issuer is not trusted")
        values = (
            evidence.evidence_id, evidence.module_id, evidence.package_digest,
            evidence.source_sha, evidence.kind.value, evidence.issuer,
            int(evidence.passed), evidence.observed_at.astimezone(timezone.utc).isoformat(),
            evidence.detail_ref, None, None,
        )
        with closing(self._connect()) as db, db:
            try:
                db.execute(
                    "INSERT INTO platform_module_readiness_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
            except sqlite3.IntegrityError:
                row = db.execute(
                    "SELECT * FROM platform_module_readiness_evidence WHERE evidence_id=?",
                    (evidence.evidence_id,),
                ).fetchone()
                if row is None or self._record(row) != evidence:
                    raise RuntimeError("evidence ID already has different semantics")
        return evidence

    def revoke(self, evidence_id: str, *, issuer: str, reason: str,
               now: datetime) -> ReadinessEvidence:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if not reason.strip():
            raise ValueError("revocation reason required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM platform_module_readiness_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
            if row is None:
                raise LookupError("unknown readiness evidence")
            evidence = self._record(row)
            if issuer not in self._trusted_issuers:
                raise PermissionError("readiness evidence issuer is not trusted")
            if evidence.issuer != issuer:
                raise PermissionError("only evidence issuer may revoke this record")
            if evidence.revoked_at is None:
                db.execute(
                    """UPDATE platform_module_readiness_evidence
                    SET revoked_at=?,revocation_reason=? WHERE evidence_id=?""",
                    (now.astimezone(timezone.utc).isoformat(), reason[:500], evidence_id),
                )
        return self.get(evidence_id)  # type: ignore[return-value]

    def get(self, evidence_id: str) -> ReadinessEvidence | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM platform_module_readiness_evidence WHERE evidence_id=?",
                (evidence_id,),
            ).fetchone()
        return None if row is None else self._record(row)

    def for_module(self, module_id: str) -> tuple[ReadinessEvidence, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM platform_module_readiness_evidence
                WHERE module_id=? ORDER BY observed_at,evidence_id""",
                (module_id,),
            ).fetchall()
        return tuple(self._record(row) for row in rows)


_RC_REQUIRED = frozenset({
    ReadinessEvidenceKind.TEST, ReadinessEvidenceKind.SECURITY_AUDIT,
    ReadinessEvidenceKind.INDEPENDENT_REVIEW, ReadinessEvidenceKind.COMPATIBILITY,
    ReadinessEvidenceKind.INTEROPERABILITY, ReadinessEvidenceKind.ROLLBACK,
})
_PRODUCTION_REQUIRED = _RC_REQUIRED | frozenset({
    ReadinessEvidenceKind.MATCHING_CI, ReadinessEvidenceKind.HOST_ACCEPTANCE,
})


def evaluate_module_readiness(
    manifest: SignedModuleManifest, lifecycle: ModuleLifecycleRecord,
    evidence: tuple[ReadinessEvidence, ...], *, source_sha: str,
) -> ModuleReadinessReport:
    if not isinstance(source_sha, str) or _SHA.fullmatch(source_sha) is None:
        raise ValueError("source_sha must be exact Git/SHA-256 digest")
    if manifest.module_id != lifecycle.module_id or (
        manifest.package_identity_digest() != lifecycle.package_digest
    ):
        return ModuleReadinessReport(
            manifest.module_id, source_sha, PlatformReadiness.BLOCKED, (),
            tuple(sorted(_PRODUCTION_REQUIRED, key=lambda item: item.value)),
            ("manifest and lifecycle package identity differ",),
        )
    relevant = tuple(item for item in evidence if (
        item.module_id == manifest.module_id
        and item.package_digest == lifecycle.package_digest
        and item.source_sha == source_sha
    ))
    failed = tuple(item for item in relevant if not item.passed and item.revoked_at is None)
    revoked = tuple(item for item in relevant if item.revoked_at is not None)
    active = {item.kind for item in relevant if item.passed and item.revoked_at is None}
    reasons: list[str] = []
    if failed:
        reasons.append("current exact-revision evidence contains a failure")
        status = PlatformReadiness.BLOCKED
    elif revoked:
        reasons.append("certification evidence was revoked")
        status = PlatformReadiness.BLOCKED
    elif lifecycle.lifecycle in {ModuleLifecycle.QUARANTINED, ModuleLifecycle.REMOVED}:
        reasons.append(f"module lifecycle is {lifecycle.lifecycle.value}")
        status = PlatformReadiness.BLOCKED
    elif _PRODUCTION_REQUIRED.issubset(active):
        status = PlatformReadiness.PRODUCTION_READY
    elif _RC_REQUIRED.issubset(active):
        status = PlatformReadiness.RELEASE_CANDIDATE
    elif lifecycle.lifecycle in {
        ModuleLifecycle.STAGED, ModuleLifecycle.INSTALLED_DISABLED,
        ModuleLifecycle.PAUSED, ModuleLifecycle.ACTIVE,
    }:
        status = PlatformReadiness.BETA
    else:
        status = PlatformReadiness.ALPHA
    missing = tuple(sorted(_PRODUCTION_REQUIRED - active, key=lambda item: item.value))
    if missing:
        reasons.append("required evidence remains missing")
    reasons.append("readiness does not authorize activation or deployment")
    return ModuleReadinessReport(
        manifest.module_id, source_sha, status,
        tuple(sorted(active, key=lambda item: item.value)), missing,
        tuple(reasons), True, False,
    )
