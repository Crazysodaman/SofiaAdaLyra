from dataclasses import dataclass
from enum import Enum

from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)


class ContinuityEventKind(str, Enum):
    """
    Deterministic classification of continuity evidence.

    Event classification describes observed system state. It does not
    assign intent, authorship, cause, or conversational significance.
    """

    INITIAL_RUNTIME = "initial_runtime"
    RUNTIME_RESUMED = "runtime_resumed"
    WORKSPACE_CHANGED = "workspace_changed"
    CONTINUITY_AND_WORKSPACE_CHANGED = (
        "continuity_and_workspace_changed"
    )
    CONTINUITY_STABLE = "continuity_stable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ContinuityEvent:
    """
    Immutable aggregate of runtime and workspace continuity evidence.

    The event is a deterministic projection of evidence already
    maintained by the operational and filesystem subsystems.

    It does not decide what Sofía should say about the evidence.
    """

    kind: ContinuityEventKind
    runtime_continuity: RuntimeContinuity
    workspace_changes: FilesystemChangeEvent | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.kind,
            ContinuityEventKind,
        ):
            raise TypeError(
                "ContinuityEvent kind must be a ContinuityEventKind."
            )

        if not isinstance(
            self.runtime_continuity,
            RuntimeContinuity,
        ):
            raise TypeError(
                "ContinuityEvent runtime_continuity must be a "
                "RuntimeContinuity."
            )

        if (
            self.workspace_changes is not None
            and not isinstance(
                self.workspace_changes,
                FilesystemChangeEvent,
            )
        ):
            raise TypeError(
                "ContinuityEvent workspace_changes must be a "
                "FilesystemChangeEvent or None."
            )

    @property
    def restart_observed(self) -> bool | None:
        return self.runtime_continuity.restart_observed

    @property
    def workspace_change_count(self) -> int:
        if self.workspace_changes is None:
            return 0

        return self.workspace_changes.total_changes

    @property
    def has_workspace_changes(self) -> bool:
        if self.workspace_changes is None:
            return False

        return self.workspace_changes.has_changes

    @property
    def evidence_status(self) -> ContinuityEvidenceStatus:
        return self.runtime_continuity.evidence_status


def create_continuity_event(
    runtime_continuity: RuntimeContinuity,
    workspace_changes: FilesystemChangeEvent | None = None,
) -> ContinuityEvent:
    """
    Create one deterministic aggregate continuity event.

    Runtime continuity and filesystem changes are combined into one
    event so downstream cognition receives coherent evidence instead
    of independent conversational triggers.
    """

    if not isinstance(
        runtime_continuity,
        RuntimeContinuity,
    ):
        raise TypeError(
            "create_continuity_event runtime_continuity must be a "
            "RuntimeContinuity."
        )

    if (
        workspace_changes is not None
        and not isinstance(
            workspace_changes,
            FilesystemChangeEvent,
        )
    ):
        raise TypeError(
            "create_continuity_event workspace_changes must be a "
            "FilesystemChangeEvent or None."
        )

    has_workspace_changes = (
        workspace_changes is not None
        and workspace_changes.has_changes
    )

    if runtime_continuity.restart_observed is True:
        if has_workspace_changes:
            kind = (
                ContinuityEventKind.CONTINUITY_AND_WORKSPACE_CHANGED
            )
        else:
            kind = ContinuityEventKind.RUNTIME_RESUMED

    elif (
        runtime_continuity.evidence_status
        is ContinuityEvidenceStatus.UNKNOWN
    ):
        if has_workspace_changes:
            kind = ContinuityEventKind.WORKSPACE_CHANGED
        else:
            kind = ContinuityEventKind.INITIAL_RUNTIME

    elif has_workspace_changes:
        kind = ContinuityEventKind.WORKSPACE_CHANGED

    else:
        kind = ContinuityEventKind.CONTINUITY_STABLE

    return ContinuityEvent(
        kind=kind,
        runtime_continuity=runtime_continuity,
        workspace_changes=workspace_changes,
    )