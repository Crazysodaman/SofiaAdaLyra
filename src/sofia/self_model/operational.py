from dataclasses import dataclass

from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)


@dataclass(frozen=True)
class SofiaOperationalSelfModel:
    """
    Runtime-facing projection of Sofía's current operational existence.

    This supplements SofiaCoreState. It does not replace the
    foundational self-model and does not grant authority.
    """

    operational_state: OperationalState
    continuity: RuntimeContinuity
    workspace_changes: FilesystemChangeEvent | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.operational_state,
            OperationalState,
        ):
            raise TypeError(
                "SofiaOperationalSelfModel operational_state must be "
                "an OperationalState."
            )

        if not isinstance(
            self.continuity,
            RuntimeContinuity,
        ):
            raise TypeError(
                "SofiaOperationalSelfModel continuity must be "
                "a RuntimeContinuity."
            )

        if (
            self.workspace_changes is not None
            and not isinstance(
                self.workspace_changes,
                FilesystemChangeEvent,
            )
        ):
            raise TypeError(
                "SofiaOperationalSelfModel workspace_changes must be "
                "a FilesystemChangeEvent or None."
            )