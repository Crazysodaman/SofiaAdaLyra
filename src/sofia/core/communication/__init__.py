"""Owner-taught communication learning (Sofia Core B05).

Shorthand interpretation records are canonical, owner-gated, append-only
readings of the owner's typing. They configure how spoken/listening surfaces
interpret ambiguous language; they never widen any authority and never act on
their own.
"""
from sofia.core.communication.service import CommunicationLearningService
from sofia.core.communication.shorthand import (
    ShorthandConcurrencyError,
    ShorthandMatch,
    ShorthandRecord,
    ShorthandStatus,
    ShorthandStore,
)

__all__ = [
    "CommunicationLearningService",
    "ShorthandConcurrencyError",
    "ShorthandMatch",
    "ShorthandRecord",
    "ShorthandStatus",
    "ShorthandStore",
]
