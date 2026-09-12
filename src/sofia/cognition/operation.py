from dataclasses import dataclass

from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext


@dataclass(frozen=True)
class CognitiveOperation:
    """
    Immutable cognitive operation containing both cognitive context
    and the authority governing that operation.

    Authority is deliberately separate from CognitiveContext.
    """

    context: CognitiveContext
    authority: Authority

    def __post_init__(self) -> None:
        if not isinstance(self.context, CognitiveContext):
            raise TypeError(
                "CognitiveOperation context must be a CognitiveContext."
            )

        if not isinstance(self.authority, Authority):
            raise TypeError(
                "CognitiveOperation authority must be an Authority."
            )