"""Workshop development requests: typed handoffs, never execution.

When Sofía decides a module is worth developing, the deliverable from
Core is a bounded WORKSHOP REQUEST: a validated manifest draft, the
declared capabilities it would offer, the tests that would let anybody
believe it works, and the sandbox and release-review requirements. The
Core never executes the module, signs packages, approves releases or
grants itself privileges; the request is data for authorized development
(Workshop/Hephaestus, MOD-DEV) and independent review.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import re
import sqlite3
from uuid import uuid4

from sofia.modules.manifest import ModuleManifest
from sofia.social.model import PrincipalContext
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


_REQUEST_ID = re.compile(r"^workshopreq:[0-9a-f-]{36}$")
_TEST_TARGET = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:/-]{0,159}$")


class WorkshopRequestStatus(str, Enum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    RETIRED = "retired"


class WorkshopRequestError(RuntimeError):
    """Race or stale revision in a workshop request write."""


def _aware(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("workshop timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class WorkshopDevelopmentRequest:
    """One revision of Sofía's typed workshop handoff."""

    request_id: str
    revision: int
    manifest: ModuleManifest
    test_targets: tuple[str, ...]
    sandbox_requirement: str
    review_requirements: tuple[str, ...]
    proposal_ref: str | None
    status: WorkshopRequestStatus
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or _REQUEST_ID.fullmatch(
            self.request_id
        ) is None:
            raise ValueError("request_id must be a canonical uuid id")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("request revision must be a positive int")
        if not isinstance(self.manifest, ModuleManifest):
            raise TypeError("manifest must be a validated ModuleManifest")
        if type(self.test_targets) is not tuple or not self.test_targets:
            raise ValueError("a development request needs a test plan")
        if (
            len(self.test_targets) > 24
            or any(
                not isinstance(item, str)
                or _TEST_TARGET.fullmatch(item) is None
                for item in self.test_targets
            )
        ):
            raise ValueError(
                "test_targets must be <=24 bounded target paths"
            )
        if (
            not isinstance(self.sandbox_requirement, str)
            or "isolated" not in self.sandbox_requirement.lower()
            or len(self.sandbox_requirement.strip()) > 300
        ):
            raise ValueError(
                "sandbox_requirement must demand an isolated bounded"
                " environment"
            )
        if type(self.review_requirements) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.review_requirements
        ):
            raise TypeError("review_requirements must be a tuple of strings")
        if self.proposal_ref is not None and (
            not isinstance(self.proposal_ref, str)
            or not self.proposal_ref.startswith("moduleproposal:")
        ):
            raise ValueError(
                "proposal_ref must be None or a moduleproposal id"
            )
        if not isinstance(self.status, WorkshopRequestStatus):
            raise TypeError("status must be WorkshopRequestStatus")
        if self.revision == 1 and self.status is not (
            WorkshopRequestStatus.PREPARED
        ):
            raise ValueError("request origin is always PREPARED")
        if _aware(self.recorded_at) != self.recorded_at:
            raise ValueError("recorded_at must be an exact UTC instant")


class WorkshopRequestStore:
    """Canonical persistence for typed workshop development requests."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self._guard = CanonicalSQLiteGuard(self.path)
        with closing(self._open()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS modules_workshop_revision (
                    request_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    manifest_json TEXT NOT NULL,
                    test_targets TEXT NOT NULL,
                    sandbox_requirement TEXT NOT NULL,
                    review_requirements TEXT NOT NULL,
                    proposal_ref TEXT,
                    status TEXT NOT NULL CHECK(status IN (
                        'prepared','submitted','retired')),
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(request_id,revision)
                );
                CREATE TABLE IF NOT EXISTS modules_workshop_current (
                    request_id TEXT PRIMARY KEY,
                    manifest_name TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(manifest_name,revision)
                );
            """)

    def _open(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _encode(record: WorkshopDevelopmentRequest) -> tuple:
        m = record.manifest
        document = {
            "name": m.name,
            "version": m.version,
            "purpose": m.purpose,
            "boundary_notes": m.boundary_notes,
            "declared_capabilities": list(m.declared_capabilities),
            "declared_dependencies": list(m.declared_dependencies),
            "authority_boundary": m.authority_boundary,
        }
        return (
            record.request_id,
            record.revision,
            json.dumps(document, sort_keys=True),
            json.dumps(list(record.test_targets)),
            record.sandbox_requirement,
            json.dumps(list(record.review_requirements)),
            record.proposal_ref,
            record.status.value,
            record.recorded_at.isoformat(),
        )

    @staticmethod
    def _decode(row: sqlite3.Row) -> WorkshopDevelopmentRequest:
        from sofia.modules.manifest import parse_manifest

        return WorkshopDevelopmentRequest(
            request_id=row["request_id"],
            revision=int(row["revision"]),
            manifest=parse_manifest(json.loads(row["manifest_json"])),
            test_targets=tuple(json.loads(row["test_targets"])),
            sandbox_requirement=row["sandbox_requirement"],
            review_requirements=tuple(
                json.loads(row["review_requirements"])
            ),
            proposal_ref=row["proposal_ref"],
            status=WorkshopRequestStatus(row["status"]),
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )

    def persist(
        self,
        record: WorkshopDevelopmentRequest,
        *,
        expected_revision: int | None,
    ) -> WorkshopDevelopmentRequest:
        with closing(self._open()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT request_id,revision FROM modules_workshop_current
                WHERE manifest_name=?""",
                (record.manifest.name,),
            ).fetchone()
            if expected_revision is None:
                if row is not None:
                    raise WorkshopRequestError(
                        "a development request already exists for this"
                        " module; revise it instead"
                    )
                if record.revision != 1:
                    raise WorkshopRequestError(
                        "creating a request requires revision 1"
                    )
            else:
                if row is None or int(row["revision"]) != expected_revision:
                    raise WorkshopRequestError(
                        "revision changed or request is absent; reload first"
                    )
                if row["request_id"] != record.request_id:
                    raise WorkshopRequestError(
                        "request identity changed; reload before revising"
                    )
            db.execute(
                """INSERT INTO modules_workshop_revision VALUES(
                ?,?,?,?,?,?,?,?,?)""",
                self._encode(record),
            )
            if row is None:
                db.execute(
                    """INSERT INTO modules_workshop_current
                    (request_id,manifest_name,revision) VALUES(?,?,?)""",
                    (record.request_id, record.manifest.name,
                     record.revision),
                )
            else:
                db.execute(
                    """UPDATE modules_workshop_current SET revision=?
                    WHERE request_id=?""",
                    (record.revision, record.request_id),
                )
        return record

    def current(self, manifest_name: str) -> (
        WorkshopDevelopmentRequest | None
    ):
        with closing(self._open()) as db:
            row = db.execute(
                """SELECT r.* FROM modules_workshop_current c
                JOIN modules_workshop_revision r
                ON r.request_id=c.request_id AND r.revision=c.revision
                WHERE c.manifest_name=?""",
                (manifest_name,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def open_requests(self, *, limit: int = 16) -> tuple:
        if not isinstance(limit, int) or not 1 <= limit <= 64:
            raise ValueError("limit must be an int in 1..64")
        with closing(self._open()) as db:
            rows = db.execute(
                """SELECT r.* FROM modules_workshop_current c
                JOIN modules_workshop_revision r
                ON r.request_id=c.request_id AND r.revision=c.revision
                WHERE r.status IN ('prepared','submitted')
                ORDER BY r.recorded_at ASC LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def new_request_id(self) -> str:
        return f"workshopreq:{uuid4()}"


class WorkshopRequestService:
    """Owner-session-gated writer for workshop development requests."""

    def __init__(self, store: WorkshopRequestStore) -> None:
        self._store = store

    @property
    def store(self) -> WorkshopRequestStore:
        return self._store

    @staticmethod
    def _require_sparks(principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "workshop request writes require the authenticated owner"
            )

    def prepare(
        self,
        principal: PrincipalContext,
        *,
        manifest: ModuleManifest,
        test_targets: tuple[str, ...],
        sandbox_requirement: str = (
            "Isolated, offline-capable sandbox environment with bounded"
            " paths; no host process escalation."
        ),
        review_requirements: tuple[str, ...] = (
            "independent code review",
            "independent security review",
            "independent release certification",
        ),
        proposal_ref: str | None = None,
        recorded_at: datetime | None = None,
    ) -> WorkshopDevelopmentRequest:
        self._require_sparks(principal)
        stamp = _aware(recorded_at) if recorded_at is not None else _aware(
            datetime.now(timezone.utc)
        )
        record = WorkshopDevelopmentRequest(
            request_id=self._store.new_request_id(),
            revision=1,
            manifest=manifest,
            test_targets=tuple(test_targets),
            sandbox_requirement=sandbox_requirement,
            review_requirements=tuple(review_requirements),
            proposal_ref=proposal_ref,
            status=WorkshopRequestStatus.PREPARED,
            recorded_at=stamp,
        )
        return self._store.persist(record, expected_revision=None)

    def mark_submitted(
        self,
        principal: PrincipalContext,
        *,
        manifest_name: str,
        expected_revision: int,
        submission_ref: str,
        recorded_at: datetime | None = None,
    ) -> WorkshopDevelopmentRequest:
        """Record that the prepared request was submitted to Workshop."""
        self._require_sparks(principal)
        if not isinstance(submission_ref, str) or not submission_ref.strip():
            raise ValueError("submission_ref must be nonempty text")
        current = self._store.current(manifest_name)
        if current is None:
            raise LookupError("unknown workshop request")
        if current.revision != expected_revision:
            raise WorkshopRequestError("revision changed; reload first")
        if current.status is not WorkshopRequestStatus.PREPARED:
            raise WorkshopRequestError(
                "only prepared requests can be marked submitted"
            )
        stamp = _aware(recorded_at) if recorded_at is not None else _aware(
            datetime.now(timezone.utc)
        )
        record = WorkshopDevelopmentRequest(
            request_id=current.request_id,
            revision=expected_revision + 1,
            manifest=current.manifest,
            test_targets=current.test_targets,
            sandbox_requirement=current.sandbox_requirement,
            review_requirements=current.review_requirements,
            proposal_ref=current.proposal_ref,
            status=WorkshopRequestStatus.SUBMITTED,
            recorded_at=stamp,
        )
        return self._store.persist(
            record, expected_revision=expected_revision,
        )

    def retire(
        self,
        principal: PrincipalContext,
        *,
        manifest_name: str,
        expected_revision: int,
        recorded_at: datetime | None = None,
    ) -> WorkshopDevelopmentRequest:
        """Retire a request or failed candidate honestly."""
        self._require_sparks(principal)
        current = self._store.current(manifest_name)
        if current is None:
            raise LookupError("unknown workshop request")
        if current.revision != expected_revision:
            raise WorkshopRequestError("revision changed; reload first")
        stamp = _aware(recorded_at) if recorded_at is not None else _aware(
            datetime.now(timezone.utc)
        )
        record = WorkshopDevelopmentRequest(
            request_id=current.request_id,
            revision=expected_revision + 1,
            manifest=current.manifest,
            test_targets=current.test_targets,
            sandbox_requirement=current.sandbox_requirement,
            review_requirements=current.review_requirements,
            proposal_ref=current.proposal_ref,
            status=WorkshopRequestStatus.RETIRED,
            recorded_at=stamp,
        )
        return self._store.persist(
            record, expected_revision=expected_revision,
        )
