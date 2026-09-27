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
    "InteractionStage",
    "InteractionVisibility",
    "PrivateInteractionGrant",
    "RepresentedInteraction",
    "TextInteractionProjection",
    "project_interaction",
    "reviewed_interaction",
)
