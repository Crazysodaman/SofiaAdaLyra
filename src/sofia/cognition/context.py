from dataclasses import dataclass

from sofia.cognition.model import CognitiveRequest
from sofia.constitution.model import Constitution
from sofia.continuity.model import (
    ContinuityEvent,
    create_continuity_event,
)
from sofia.embodiment.model import Embodiment
from sofia.filesystem.changes import FilesystemChangeEvent
from sofia.filesystem.model import FilesystemResult
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.operational.model import (
    OperationalState,
    RuntimeContinuity,
)
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import SofiaCoreState
from sofia.self_model.operational import SofiaOperationalSelfModel


@dataclass(frozen=True)
class CognitiveContext:
    """
    Immutable projection of persistent Sofía state and operational
    information for one cognitive operation.
    """

    request: CognitiveRequest
    identity: SofiaIdentity | None = None
    personality: PersonalityProfile | None = None
    memories: tuple[MemoryRecord, ...] = ()
    constitution: Constitution | None = None
    embodiment: Embodiment | None = None
    core_state: SofiaCoreState | None = None
    operational_state: OperationalState | None = None
    runtime_continuity: RuntimeContinuity | None = None
    filesystem_results: tuple[FilesystemResult, ...] = ()
    workspace_changes: FilesystemChangeEvent | None = None
    operational_self_model: SofiaOperationalSelfModel | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, CognitiveRequest):
            raise TypeError(
                "CognitiveContext request must be a CognitiveRequest."
            )

        if (
            self.identity is not None
            and not isinstance(self.identity, SofiaIdentity)
        ):
            raise TypeError(
                "CognitiveContext identity must be a SofiaIdentity."
            )

        if (
            self.personality is not None
            and not isinstance(self.personality, PersonalityProfile)
        ):
            raise TypeError(
                "CognitiveContext personality must be a PersonalityProfile."
            )

        if not isinstance(self.memories, tuple):
            raise TypeError(
                "CognitiveContext memories must be a tuple."
            )

        for memory in self.memories:
            if not isinstance(memory, MemoryRecord):
                raise TypeError(
                    "CognitiveContext memories must contain "
                    "MemoryRecord instances."
                )

        if (
            self.constitution is not None
            and not isinstance(self.constitution, Constitution)
        ):
            raise TypeError(
                "CognitiveContext constitution must be a Constitution."
            )

        if (
            self.embodiment is not None
            and not isinstance(self.embodiment, Embodiment)
        ):
            raise TypeError(
                "CognitiveContext embodiment must be an Embodiment."
            )

        if (
            self.core_state is not None
            and not isinstance(self.core_state, SofiaCoreState)
        ):
            raise TypeError(
                "CognitiveContext core_state must be a SofiaCoreState."
            )

        if (
            self.operational_state is not None
            and not isinstance(
                self.operational_state,
                OperationalState,
            )
        ):
            raise TypeError(
                "CognitiveContext operational_state must be "
                "an OperationalState."
            )

        if (
            self.runtime_continuity is not None
            and not isinstance(
                self.runtime_continuity,
                RuntimeContinuity,
            )
        ):
            raise TypeError(
                "CognitiveContext runtime_continuity must be "
                "a RuntimeContinuity."
            )

        if not isinstance(self.filesystem_results, tuple):
            raise TypeError(
                "CognitiveContext filesystem_results must be a tuple."
            )

        for result in self.filesystem_results:
            if not isinstance(result, FilesystemResult):
                raise TypeError(
                    "CognitiveContext filesystem_results must contain "
                    "FilesystemResult instances."
                )

        if (
            self.workspace_changes is not None
            and not isinstance(
                self.workspace_changes,
                FilesystemChangeEvent,
            )
        ):
            raise TypeError(
                "CognitiveContext workspace_changes must be a "
                "FilesystemChangeEvent or None."
            )

        if (
            self.operational_self_model is not None
            and not isinstance(
                self.operational_self_model,
                SofiaOperationalSelfModel,
            )
        ):
            raise TypeError(
                "CognitiveContext operational_self_model must be a "
                "SofiaOperationalSelfModel or None."
            )

    @property
    def continuity_event(self) -> ContinuityEvent | None:
        """
        Return one aggregate continuity event when runtime continuity
        evidence is available.

        The event is derived from deterministic evidence already present
        in this context. It does not create additional observations.
        """

        if self.runtime_continuity is None:
            return None

        return create_continuity_event(
            runtime_continuity=self.runtime_continuity,
            workspace_changes=self.workspace_changes,
        )