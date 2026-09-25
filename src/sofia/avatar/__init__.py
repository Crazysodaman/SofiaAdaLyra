"""Headless representation metadata; not a rendered avatar or an art asset."""
from .wardrobe import (
    Garment, Layer, Outfit, PreviewRequest, Wardrobe, WardrobeError,
    WardrobeConflict, VisibilityDenied,
)
__all__ = [
    "Garment", "Layer", "Outfit", "PreviewRequest", "Wardrobe",
    "WardrobeError", "WardrobeConflict", "VisibilityDenied",
]

from .scene import Actor, Action, Prop, Proposal, Scene, SceneConflict, SceneDenied, SceneError

__all__ += ["Actor", "Action", "Prop", "Proposal", "Scene", "SceneConflict", "SceneDenied", "SceneError"]

from .shared_wardrobe_state import (
    PresentationMode, SharedWardrobeState, TransitionStatus, WardrobeChange,
    WardrobeState, WardrobeStateConflict, WardrobeStateDenied,
    WardrobeStateError, WardrobeItemProjection, WardrobeTextProjection,
)

__all__ += [
    "PresentationMode", "SharedWardrobeState", "TransitionStatus",
    "WardrobeChange", "WardrobeState", "WardrobeStateConflict",
    "WardrobeStateDenied", "WardrobeStateError", "WardrobeItemProjection",
    "WardrobeTextProjection",
]

from .wardrobe_routine import (
    Activity, Cadence, ChangeOrigin, ClothingAppraisal, OutfitPlan, OutfitPlanner,
    OutfitProposal, Preference, PreferenceActor, PreferenceTarget, Season,
    Sentiment, WardrobeContext, Weather, WeatherObservation, WornEvidence,
    appraise_clothing_change, period_key,
)

__all__ += [
    "Activity", "Cadence", "ChangeOrigin", "ClothingAppraisal", "OutfitPlan",
    "OutfitPlanner", "OutfitProposal", "Preference", "PreferenceActor",
    "PreferenceTarget", "Season", "Sentiment", "WardrobeContext", "Weather",
    "WeatherObservation", "WornEvidence", "appraise_clothing_change", "period_key",
]

from .wardrobe_catalog import (
    DRAFT_STATUS, GarmentBlueprint, RequestStatus, StyleInput,
    WardrobePrebuild, build_starter_wardrobe,
)

__all__ += [
    "DRAFT_STATUS", "GarmentBlueprint", "RequestStatus", "StyleInput",
    "WardrobePrebuild", "build_starter_wardrobe",
]

from .style_context import StyleContext, project_style_context

__all__ += ["StyleContext", "project_style_context"]

from .starter_user_preferences import (
    SPARKS_LIKED_OUTFIT_SOURCE_IDS, build_sparks_starter_wardrobe,
    confirmed_sparks_outfit_likes, with_sparks_outfit_likes,
)

__all__ += [
    "SPARKS_LIKED_OUTFIT_SOURCE_IDS", "build_sparks_starter_wardrobe",
    "confirmed_sparks_outfit_likes", "with_sparks_outfit_likes",
]

from .lounge_graphic_tee import (
    GRAPHIC_OUTFIT_ID, GRAPHIC_REQUEST_SOURCE_ID, GRAPHIC_TEE_ID,
    GraphicLoungeVariation, build_graphic_lounge_variation,
)

__all__ += [
    "GRAPHIC_OUTFIT_ID", "GRAPHIC_REQUEST_SOURCE_ID", "GRAPHIC_TEE_ID",
    "GraphicLoungeVariation", "build_graphic_lounge_variation",
]


from .presentation import (
    AppearanceState, AttireMode, AudienceScope, PresentationAuthority,
    PresentationChange, PresentationConflict, PresentationDenied,
    PresentationError, PresentationProjection, PresentationState,
    PrivatePresentationGrant,
)
from .presentation_store import PresentationStore, PresentationStoreError
from .runtime_state import (
    PresentationRuntimeBundle, load_or_bootstrap_presentation,
    presentation_state_path,
)
from .wardrobe_routine import EmotionStyleInfluence

__all__ += [
    "AppearanceState", "AttireMode", "AudienceScope", "PresentationAuthority",
    "PresentationChange", "PresentationConflict", "PresentationDenied",
    "PresentationError", "PresentationProjection", "PresentationState",
    "PrivatePresentationGrant", "PresentationStore", "PresentationStoreError",
    "PresentationRuntimeBundle", "load_or_bootstrap_presentation",
    "presentation_state_path", "EmotionStyleInfluence",
]
