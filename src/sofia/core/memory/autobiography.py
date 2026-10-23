"""Provenance-aware autobiographical timeline over canonical records.

The timeline is a bounded, read-only assembly of Sofía's own history from
two already-provenance'd sources: reviewed promoted memory candidates
(with all of MEM's staleness, revocation, and scope guards rechecked) and
canonical LIFE experience records. No entry is invented, reworded, or
summarized beyond the canonical text; each entry keeps its anchor so its
original record remains authoritative. Convenience reads from foreign
audiences fail closed.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
import json
import sqlite3

from sofia.core.memory.provenance import CandidateStatus
from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
from sofia.core.memory.significance import MarkStatus, SignificantMemoryStore
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


_LOCAL_AUDIENCES = frozenset({"local:text", "local:terminal"})


@dataclass(frozen=True, slots=True)
class AutobiographicalEntry:
    """One bounded factual entry anchored to a canonical record."""

    occurred_at: datetime
    kind: str
    summary: str
    anchor: str
    significance: float | None


class AutobiographyTimeline:
    """Bounded newest-first personal history with eligibility rechecks."""

    def __init__(
        self, *,
        state_path,
        candidate_store: DurableMemoryCandidateStore,
        significance_store: SignificantMemoryStore,
        experience_audience_id: str = "local:text",
    ) -> None:
        if not isinstance(candidate_store, DurableMemoryCandidateStore):
            raise TypeError("candidate_store must be a DurableMemoryCandidateStore")
        if not isinstance(significance_store, SignificantMemoryStore):
            raise TypeError("significance_store must be a SignificantMemoryStore")
        self.path = state_path
        self._candidates = candidate_store
        self._significance = significance_store
        self._audience = experience_audience_id
        self._guard = CanonicalSQLiteGuard(state_path)

    def _local_memories(
        self, *, principal_id: str, audience_id: str, limit: int,
        batch_size: int, scan_cap: int,
    ) -> list[tuple[UUID, str]]:
        """Eligibility-gated promoted candidates via the keyset stream.

        `iter_promoted_summaries` carries the certified pass through the
        store's attested-source guards; the scan cap keeps this reader
        bounded even when a long history already exists.
        """
        collected: list[tuple[UUID, str]] = []
        for identifier, content in self._candidates.iter_promoted_summaries(
            principal_id=principal_id, audience_id=audience_id,
            batch_size=batch_size,
        ):
            collected.append((identifier, content))
            if len(collected) >= scan_cap:
                break
        if len(collected) > limit:
            collected = collected[-limit:]
        return collected

    def _memory_entries(
        self, *, principal: PrincipalContext, limit: int,
        batch_size: int, scan_cap: int,
    ) -> tuple[AutobiographicalEntry, ...]:
        principal_id, audience_id = principal.principal_id, principal.audience_id
        eligible = self._local_memories(
            principal_id=principal_id, audience_id=audience_id,
            limit=limit, batch_size=batch_size, scan_cap=scan_cap,
        )
        marked = {
            mark.candidate_id: mark.significance
            for mark in self._significance.active_marks(
                principal_id=principal_id, audience_id=audience_id,
            )
            if mark.status is MarkStatus.ACTIVE
        }
        entries: list[AutobiographicalEntry] = []
        for identifier, content in eligible:
            # The stream already rechecked eligibility inside its own SQL
            # batch; re-read the canonical candidate and reverify status,
            # scope and eligibility at the final handoff as MEM requires.
            current = self._candidates.get(identifier)
            if (
                current is None
                or current.content != content
                or current.principal_id != principal_id
                or current.audience_id not in (None, audience_id)
                or self._candidates.status(identifier) is not CandidateStatus.PROMOTED
                or not self._candidates.is_recall_eligible(identifier)
            ):
                continue
            entries.append(AutobiographicalEntry(
                occurred_at=current.created_at,
                kind="memory",
                summary=current.content,
                anchor=f"memory:{current.candidate_id}",
                significance=marked.get(current.candidate_id),
            ))
        return tuple(entries)

    def _experience_entries(
        self, *, limit: int, now: datetime,
    ) -> tuple[AutobiographicalEntry, ...]:
        from sofia.life.store import LifeStore
        store = LifeStore(self.path)
        experiences = store.experiences(
            audience_id=self._audience, include_private=True, limit=limit,
        )
        entries: list[AutobiographicalEntry] = []
        for record in experiences:
            if record.recorded_at > now or record.occurred_at > now:
                continue
            entries.append(AutobiographicalEntry(
                occurred_at=record.occurred_at,
                kind="experience",
                summary=record.summary,
                anchor=f"experience:{record.experience_id.removeprefix('experience:')}",
                significance=None,
            ))
        return tuple(entries)

    def _episode_entries(
        self, *, principal: PrincipalContext, limit: int, now: datetime,
    ) -> tuple[AutobiographicalEntry, ...]:
        """Current generalization-episode outcomes as bounded episode entries.

        GA experience episodes are separate canonical projections owned by
        `AdvancedGeneralizationStore` with their own retention, revocation,
        expiry and correction lifecycle. This read-only surface may quote
        only rows that are current, unexpired, and audience-exact at this
        very read, and only the canonical outcome-phase summary text —
        never a rewrite or synthesis. Any row failing those conditions
        simply does not appear; the GA lifecycle remains the sole writer.
        """
        if principal.audience_id is None:
            return ()
        with closing(self._guard.connect(timeout=10)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='ga_experience_episode'",
            ).fetchone()
            if exists is None:
                return ()
            rows = db.execute(
                """SELECT episode_id,phases_json,occurred_at
                FROM ga_experience_episode
                WHERE principal_id=? AND audience_id=?
                AND status='current' AND retention_until>?
                ORDER BY occurred_at DESC, episode_id LIMIT ?""",
                (principal.principal_id, principal.audience_id,
                 now.isoformat(), limit),
            ).fetchall()
        entries: list[AutobiographicalEntry] = []
        for row in rows:
            try:
                phases = json.loads(row["phases_json"])
                occurred = datetime.fromisoformat(row["occurred_at"])
            except (ValueError, TypeError):
                continue
            outcome = next(
                (
                    phase for phase in phases
                    if isinstance(phase, Mapping)
                    and phase.get("kind") == "outcome"
                    and isinstance(phase.get("summary"), str)
                    and phase["summary"].strip()
                ),
                None,
            )
            if outcome is None or occurred > now:
                continue
            entries.append(AutobiographicalEntry(
                occurred_at=occurred,
                kind="episode",
                summary=outcome["summary"],
                anchor=f"ga-episode:{row['episode_id'].removeprefix('ga-episode:')}",
                significance=None,
            ))
        return tuple(entries)

    def entries(
        self, *, principal: PrincipalContext, limit: int = 64,
        scanner_batch_size: int = 128,
    ) -> tuple[AutobiographicalEntry, ...]:
        """Newest-first bounded autobiography for a private local session."""
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be a PrincipalContext")
        if type(limit) is not int or not 1 <= limit <= 256:
            raise ValueError("limit must be an int in 1..256")
        if type(scanner_batch_size) is not int or not 1 <= scanner_batch_size <= 512:
            raise ValueError("scanner_batch_size must be an int in 1..512")
        if (
            principal.audience_kind is not AudienceKind.PRIVATE
            or principal.audience_id not in _LOCAL_AUDIENCES
        ):
            return ()
        now = datetime.now(timezone.utc)
        scan_cap = max(256, limit * 8)
        entries = [
            *self._memory_entries(
                principal=principal, limit=limit,
                batch_size=scanner_batch_size, scan_cap=scan_cap,
            ),
            *self._experience_entries(limit=limit, now=now),
            *self._episode_entries(
                principal=principal, limit=limit, now=now,
            ),
        ]
        entries.sort(
            key=lambda item: (-item.occurred_at.timestamp(), item.kind, item.anchor),
        )
        return tuple(entries[:limit])
