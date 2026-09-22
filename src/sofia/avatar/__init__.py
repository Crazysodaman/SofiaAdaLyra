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
