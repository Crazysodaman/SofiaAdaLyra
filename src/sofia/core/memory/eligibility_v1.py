"""Opt-in CORE-003 V1 eligibility fence for disposable, owner-reviewed memory.

This module is deliberately not wired into production composition. An operator
must separately approve any protected-state migration or runtime activation.
A legacy PROMOTED bit alone never proves reviewed provenance under V1.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard, require_existing_sqlite


POLICY_VERSION = 1


class MemoryEligibilityVersionError(RuntimeError):
    """Missing, downgraded or unsupported canonical memory eligibility policy."""


def _require_private_owner(approved_by: PrincipalContext) -> None:
    """Caller must first authenticate principal at the application boundary."""
    if (
        not isinstance(approved_by, PrincipalContext)
        or approved_by.principal_id != SPARKS_PRINCIPAL_ID
        or approved_by.audience_kind is not AudienceKind.PRIVATE
        or not approved_by.audience_id
    ):
        raise PermissionError("private authenticated owner review required")


def install_disposable_policy_v1(
    state_path: Path | str, *,
    approved_by: PrincipalContext,
    expected_version: int | None = None,
) -> int:
    """Owner-confirmed, compare-and-swap test-state migration; never auto-run.

    This is a version receipt INSIDE the canonical SQLite state, not a portable
    trust root or a single-writer lease. Independent Platform authority is still
    required before any protected-state use.
    """
    _require_private_owner(approved_by)
    if expected_version is not None and (
        type(expected_version) is not int or expected_version != POLICY_VERSION
    ):
        raise MemoryEligibilityVersionError("memory eligibility downgrade refused")
    guard = CanonicalSQLiteGuard(state_path)
    with closing(guard.connect()) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS core_memory_eligibility_policy ("
            "singleton INTEGER PRIMARY KEY CHECK (singleton=1),"
            "version INTEGER NOT NULL CHECK (version>=1),"
            "reviewed_by TEXT NOT NULL, audience_id TEXT NOT NULL,"
            "updated_at TEXT NOT NULL)"
        )
        row = db.execute(
            "SELECT version,reviewed_by,audience_id FROM "
            "core_memory_eligibility_policy WHERE singleton=1"
        ).fetchone()
        observed = None if row is None else row[0]
        if observed != expected_version:
            raise MemoryEligibilityVersionError(
                "policy version changed; explicit reviewed migration required"
            )
        if row is not None and tuple(row[1:]) != (
            approved_by.principal_id, approved_by.audience_id,
        ):
            raise PermissionError("policy revision belongs to another owner audience")
        if observed is None:
            db.execute(
                "INSERT INTO core_memory_eligibility_policy "
                "(singleton,version,reviewed_by,audience_id,updated_at) "
                "VALUES(1,?,?,?,?)",
                (
                    POLICY_VERSION, approved_by.principal_id,
                    approved_by.audience_id, datetime.now(timezone.utc).isoformat(),
                ),
            )
        elif observed != POLICY_VERSION:
            raise MemoryEligibilityVersionError("policy version downgrade refused")
    return POLICY_VERSION


class ReviewedMemoryEligibilityV1:
    """Strict memory recall gate; opt in per disposable MemorySystem instance.

    An absent policy marker, including one from an older restored backup,
    is an error, never permission to silently fall back to legacy retrieval.
    """

    version = POLICY_VERSION

    def __init__(self, state_path: Path | str, *, minimum_version: int = 1):
        if type(minimum_version) is not int or minimum_version != POLICY_VERSION:
            raise MemoryEligibilityVersionError("unsupported/downgraded policy version")
        self._guard = CanonicalSQLiteGuard(state_path)
        self.minimum_version = minimum_version

    def assert_same_canonical_state(self, candidate_store_path: Path | str) -> None:
        """Never combine policy approval from one Core with memory from another."""
        pinned_path = self._guard.validate()
        requested_path, _ = require_existing_sqlite(candidate_store_path)
        if requested_path != pinned_path:
            raise PermissionError(
                "memory eligibility policy belongs to another canonical state"
            )

    def require_current(self) -> None:
        with closing(self._guard.connect(read_only=True)) as db:
            try:
                row = db.execute(
                    "SELECT version FROM core_memory_eligibility_policy "
                    "WHERE singleton=1"
                ).fetchone()
            except sqlite3.Error as exc:
                raise MemoryEligibilityVersionError(
                    "versioned memory policy absent: restored snapshot is ineligible"
                ) from exc
        if (
            row is None
            or type(row[0]) is not int
            or row[0] != POLICY_VERSION
            or row[0] < self.minimum_version
        ):
            raise MemoryEligibilityVersionError(
                "memory policy missing, downgraded or unsupported"
            )

    def allows(self, candidate_id: UUID) -> bool:
        if not isinstance(candidate_id, UUID):
            raise TypeError("memory candidate ID must be UUID")
        self.require_current()
        with closing(self._guard.connect(read_only=True)) as db:
            try:
                row = db.execute(
                    "SELECT 1 FROM memory_candidate AS c "
                    "INNER JOIN memory_candidate_source_review AS r "
                    "ON r.candidate_id=c.candidate_id "
                    "WHERE c.candidate_id=? AND c.status='promoted' "
                    "AND c.principal_id=r.principal_id "
                    "AND c.audience_id=r.audience_id",
                    (str(candidate_id),),
                ).fetchone()
            except sqlite3.Error as exc:
                raise MemoryEligibilityVersionError(
                    "reviewed-memory attestation schema unavailable"
                ) from exc
        return row is not None
