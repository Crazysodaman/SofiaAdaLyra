from dataclasses import dataclass

from sofia.cognition.model import CognitiveRequest
from sofia.constitution.model import Constitution
from sofia.embodiment.model import Embodiment
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.operational.model import OperationalState
from sofia.personality.model import PersonalityProfile
from sofia.self_model.model import SofiaCoreState


@dataclass(frozen=True)
class CognitiveContext:
    """
    Immutable projection of persistent Sofía state and operational
    information for one cognitive operation.

    CognitiveContext is not Sofía's persistent state. It contains only
    information explicitly supplied to a particular cognitive operation.
    """

    request: CognitiveRequest
    identity: SofiaIdentity | None = None
    personality: PersonalityProfile | None = None
    memories: tuple[MemoryRecord, ...] = ()
    constitution: Constitution | None = None
    embodiment: Embodiment | None = None
    core_state: SofiaCoreState | None = None
    operational_state: OperationalState | None = None

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