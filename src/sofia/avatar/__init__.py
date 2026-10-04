"""Headless representation metadata; not a rendered avatar or an art asset."""
from .wardrobe import (
    Garment, Layer, Outfit, PreviewRequest, Wardrobe, WardrobeError,
    WardrobeConflict, VisibilityDenied,
)
__all__ = [
    "Garment", "Layer", "Outfit", "PreviewRequest", "Wardrobe",
    "WardrobeError", "WardrobeConflict", "VisibilityDenied",
]

from .wardrobe_planner import (
    Activity, Cadence, ChangeOrigin, ClothingAppraisal, OutfitPlan, OutfitPlanner,
    OutfitProposal, Preference, PreferenceActor, PreferenceTarget, Season,
    Sentiment, WardrobeContext, Weather, WeatherObservation, WornEvidence,
    appraise_clothing_change, period_key, wardrobe_emotion_influences,
)

__all__ += [
    "Activity", "Cadence", "ChangeOrigin", "ClothingAppraisal", "OutfitPlan",
    "OutfitPlanner", "OutfitProposal", "Preference", "PreferenceActor",
    "PreferenceTarget", "Season", "Sentiment", "WardrobeContext", "Weather",
    "WeatherObservation", "WornEvidence", "appraise_clothing_change", "period_key",
    "wardrobe_emotion_influences",
]

from .wardrobe_catalog import (
    DRAFT_STATUS, GRAPHIC_OUTFIT_ID, GRAPHIC_REQUEST_SOURCE_ID, GRAPHIC_TEE_ID,
    SPARKS_LIKED_OUTFIT_SOURCE_IDS, ClosetCategory, GarmentBlueprint,
    GraphicLoungeVariation, PieceSpec, RequestStatus, StyleInput,
    WardrobePrebuild, all_closet_categories, build_graphic_lounge_variation,
    build_sparks_starter_wardrobe, build_starter_wardrobe,
    confirmed_sparks_outfit_likes, generated_bikini_outfits,
    generated_bikini_piece_specs, generated_piece_specs,
    generated_seasonal_outfits, with_sparks_outfit_likes,
)

__all__ += [
    "DRAFT_STATUS", "GRAPHIC_OUTFIT_ID", "GRAPHIC_REQUEST_SOURCE_ID",
    "GRAPHIC_TEE_ID", "SPARKS_LIKED_OUTFIT_SOURCE_IDS", "ClosetCategory",
    "GarmentBlueprint", "GraphicLoungeVariation", "PieceSpec", "RequestStatus",
    "StyleInput", "WardrobePrebuild", "all_closet_categories",
    "build_graphic_lounge_variation", "build_sparks_starter_wardrobe",
    "build_starter_wardrobe", "confirmed_sparks_outfit_likes",
    "generated_bikini_outfits", "generated_bikini_piece_specs",
    "generated_piece_specs", "generated_seasonal_outfits",
    "with_sparks_outfit_likes",
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
from .wardrobe_planner import EmotionStyleInfluence

__all__ += [
    "AppearanceState", "AttireMode", "AudienceScope", "PresentationAuthority",
    "PresentationChange", "PresentationConflict", "PresentationDenied",
    "PresentationError", "PresentationProjection", "PresentationState",
    "PrivatePresentationGrant", "PresentationStore", "PresentationStoreError",
    "PresentationRuntimeBundle", "load_or_bootstrap_presentation",
    "presentation_state_path", "EmotionStyleInfluence",
]

from .presentation_routine import HeadlessPresentationRoutine, PresentationRoutineResult

__all__ += ["HeadlessPresentationRoutine", "PresentationRoutineResult"]

from .wardrobe_matrix import (
    WardrobeMatrixCell,
    WardrobeSlotMatrix,
    build_wardrobe_matrix,
)

__all__ += [
    "WardrobeMatrixCell",
    "WardrobeSlotMatrix",
    "build_wardrobe_matrix",
]

from .self_fact_query import AvatarSelfFactAnswer, AvatarSelfFactResolver

__all__ += ["AvatarSelfFactAnswer", "AvatarSelfFactResolver"]

