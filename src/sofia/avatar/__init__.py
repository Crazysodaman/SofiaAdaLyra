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
