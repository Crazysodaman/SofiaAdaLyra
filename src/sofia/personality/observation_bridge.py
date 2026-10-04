"""Translate trusted, typed observations into emotional and reflection records.

No text classification, implicit authorization, background activity or delivery.
Only callers holding real observation objects
should invoke these functions. Models have no direct access to this bridge.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.emotion.journal import EmotionalJournal
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
