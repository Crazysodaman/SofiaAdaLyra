"""Optional avatar and text share the same interaction semantics."""

from sofia.interaction.core import (
    GESTURES, REGISTRY_VERSION, InteractionDecision, InteractionEngine,
    InteractionEvent, Region,
)

__all__ = (
    "GESTURES", "REGISTRY_VERSION", "InteractionDecision", "InteractionEngine",
    "InteractionEvent", "Region",
)


from sofia.interaction.representation import (
    AvatarInteractionIntent,
    InteractionProjectionBundle,
    InteractionProjectionDenied,
    InteractionPhase,
    InteractionStage,
    InteractionVisibility,
    PrivateInteractionGrant,
    RepresentedInteraction,
    TextInteractionProjection,
    project_interaction,
    reviewed_interaction,
)

__all__ += (
    "AvatarInteractionIntent",
    "InteractionProjectionBundle",
    "InteractionProjectionDenied",
    "InteractionPhase",
    "InteractionStage",
    "InteractionVisibility",
    "PrivateInteractionGrant",
    "RepresentedInteraction",
    "TextInteractionProjection",
    "project_interaction",
    "reviewed_interaction",
)


from sofia.interaction.initiative import (
    CanonicalInitiativePlanner,
    CanonicalInteractionProposal,
    InitiativeSource,
    InteractionReactionLink,
)
from sofia.interaction.target_body import (
    RepresentedTargetBody,
    TargetRegion,
)

__all__ += (
    "CanonicalInitiativePlanner",
    "CanonicalInteractionProposal",
    "InitiativeSource",
    "InteractionReactionLink",
    "RepresentedTargetBody",
    "TargetRegion",
)
