"""Translate trusted, typed observations into emotional and reflection records.

No text classification, implicit authorization, background activity or delivery.
Only callers holding real observation objects or verified test-run results
should invoke these functions. Models have no direct access to this bridge.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.personality.emotion import EmotionalJournal
from sofia.personality.reflection import ReflectionJournal


def record_workspace_observation(
    *, event: FilesystemChangeEvent, emotions: EmotionalJournal,
    reflections: ReflectionJournal, ignored_paths: tuple[Path, ...] = (),
) -> str | None:
    """Record one observed snapshot delta, not assumed intent or causality.

    No baseline means changes cannot be established. Idempotency keys include
    snapshot time and changed-path identities, not runtime startup time.
    """
    if not isinstance(event, FilesystemChangeEvent):
        raise TypeError("A FilesystemChangeEvent is required.")
    if not isinstance(emotions, EmotionalJournal) or not isinstance(reflections, ReflectionJournal):
        raise TypeError("EmotionalJournal and ReflectionJournal are required.")
    if not isinstance(ignored_paths, tuple) or any(
        not isinstance(path, Path) for path in ignored_paths
    ):
        raise TypeError("Ignored paths must be a tuple of Paths.")
    if not event.baseline_available or not event.has_changes:
        return None
    # Prevent a journal write from becoming the next boot's emotional event.
    # SQLite can create three companion files beside its configured state DB.
    ignored = tuple(str(path.resolve()).casefold() for path in ignored_paths)
    companions = ("", "-wal", "-shm", "-journal")
    def relevant(change):
        candidate = str(change.path.resolve()).casefold()
        return not any(candidate == root + suffix for root in ignored for suffix in companions)
    added = tuple(change for change in event.new if relevant(change))
    modified = tuple(change for change in event.modified if relevant(change))
    removed = tuple(change for change in event.removed if relevant(change))
    if not (added or modified or removed):
        return None
    when = event.current_observed_at
    if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("The snapshot timestamp must be timezone-aware.")
    paths = sorted(
        (change.kind.value, str(change.path))
        for change in (*added, *modified, *removed)
    )
    digest = sha256(json.dumps([when.isoformat(), paths], ensure_ascii=False).encode("utf-8")).hexdigest()[:32]
    reference = f"workspace-snapshot:{digest}"
    description = (
        "Workspace comparison observed "
        f"{len(added)} added, {len(modified)} modified, "
        f"and {len(removed)} removed paths."
    )
    labels = ("curiosity", "caution") if removed else ("curiosity",)
    event_id = f"workspace-change:{digest}"
    emotions.record(
        event_id=event_id, occurred_at=when, source="observed",
        evidence_ref=reference, description=description, emotions=labels,
    )
    reflections.record_thought(
        thought_id=f"workspace-thought:{digest}", kind="observation",
        subject="Observed workspace changes",
        content=f"{description} Cause, authorship, and significance are not established.",
        evidence_refs=(event_id,), emotions=labels, created_at=when,
    )
    return event_id


def record_verified_test_run(
    *, run_id: str, evidence_ref: str, completed_at: datetime,
    passed: int, failed: int, skipped: int, emotions: EmotionalJournal,
    reflections: ReflectionJournal,
) -> str:
    """Ingest explicit result counts supplied by a trusted test-run producer.

    The bridge cannot verify that a caller actually executed pytest. A chat
    claim or LLM-generated answer must never be passed as observed evidence.
    """
    for label, value in (("run_id", run_id), ("evidence_ref", evidence_ref)):
        if (not isinstance(value, str) or not 0 < len(value.strip()) <= 120
                or any(ch in value for ch in "\x00\r\n")):
            raise ValueError(f"{label} must be a nonempty single-line identifier.")
    if not isinstance(completed_at, datetime) or completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise ValueError("Test completion time must be timezone-aware.")
    if any(type(n) is not int or n < 0 for n in (passed, failed, skipped)):
        raise ValueError("Test counts must be nonnegative integers.")
    if passed + failed + skipped == 0:
        raise ValueError("An empty test result is not a completed test run.")
    if not isinstance(emotions, EmotionalJournal) or not isinstance(reflections, ReflectionJournal):
        raise TypeError("EmotionalJournal and ReflectionJournal are required.")
    description = f"Recorded test run: {passed} passed, {failed} failed, {skipped} skipped."
    labels = ("concern", "curiosity", "determination") if failed else (
        ("joy", "contentment") if passed else ("uncertainty", "curiosity")
    )
    event_id = f"test-run:{run_id}"
    emotions.record(
        event_id=event_id, occurred_at=completed_at, source="observed",
        evidence_ref=evidence_ref, description=description, emotions=labels,
    )
    reflections.record_thought(
        thought_id=f"test-thought:{run_id}", kind="observation",
        subject="Recorded test outcome", content=description,
        evidence_refs=(event_id,), emotions=labels, created_at=completed_at,
    )
    return event_id


def record_user_reappraisal(
    *, event_id: str, message_id: str, clarification: str,
    new_emotions: tuple[str, ...], revised_at: datetime,
    journal: EmotionalJournal,
) -> None:
    """Preserve original appraisal and append a user's later clarification.

    Caller must associate the clarification with a real persisted user message.
    This does not infer corrections from free-form conversation automatically.
    """
    for label, value in (("event_id", event_id), ("message_id", message_id)):
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise ValueError(f"{label} is required (max 100 characters).")
    if (not isinstance(clarification, str) or not 0 < len(clarification.strip()) <= 160
            or any(ch in clarification for ch in "\x00\r\n")):
        raise ValueError("A concise, single-line user clarification is required.")
    if not isinstance(journal, EmotionalJournal):
        raise TypeError("An EmotionalJournal is required.")
    journal.revise(
        event_id=event_id, emotions=new_emotions,
        reason=f"User clarification ({message_id}): {clarification}",
        revised_at=revised_at,
    )
