"""Normalize internal state-file noise at the runtime/application boundary.

The raw filesystem observation stays in the observation store. The runtime's
conversational projection and pending continuity event must agree about what
was externally relevant. Suppress only the configured conversation and virtual
lab SQLite files and their exact sidecars, never unrelated database changes.
"""
from __future__ import annotations

from pathlib import Path

from sofia.continuity.model import (
    ContinuityEventKind, create_continuity_event,
)
from sofia.filesystem.change_filter import exclude_internal_state_changes
from sofia.interaction.world_setup import lab_state_path

_AWARENESS_KINDS = frozenset({
    ContinuityEventKind.RUNTIME_RESUMED,
    ContinuityEventKind.WORKSPACE_CHANGED,
    ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED,
})


def normalize_runtime_workspace_awareness(runtime) -> None:
    """Filter only owned SQLite files before the first model request.

    Only call after runtime.start and before conversation.open/start. A mock
    runtime without workspace evidence remains unchanged; a real event without
    continuity evidence fails visibly rather than claiming an unknown state.
    """
    changes = getattr(runtime, "workspace_changes", None)
    if changes is None:
        return
    state = Path(runtime.configuration.state_path)
    filtered = exclude_internal_state_changes(changes, state_path=state)
    filtered = exclude_internal_state_changes(filtered, state_path=lab_state_path(state))
    if filtered is changes:
        return
    continuity = runtime.runtime_continuity
    if continuity is None:
        raise RuntimeError("Workspace changes exist without runtime continuity evidence.")
    event = create_continuity_event(
        runtime_continuity=continuity, workspace_changes=filtered,
    )
    runtime._workspace_changes = filtered
    runtime._pending_continuity_event = (
        event if event.kind in _AWARENESS_KINDS else None
    )
