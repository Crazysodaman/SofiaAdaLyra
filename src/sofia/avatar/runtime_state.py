"""Bootstrap and persistence helpers for headless AVATAR presentation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sofia.embodiment.model import Embodiment

from .presentation import AppearanceState, PresentationAuthority
from .presentation_store import PresentationStore
from .wardrobe_catalog import WardrobePrebuild, build_starter_wardrobe


@dataclass(frozen=True, slots=True)
class PresentationRuntimeBundle:
    authority: PresentationAuthority
    store: PresentationStore
    catalog: WardrobePrebuild


def _appearance_from_embodiment(embodiment: Embodiment) -> AppearanceState:
    if not isinstance(embodiment, Embodiment):
        raise TypeError("canonical Embodiment is required")
    appearance = dict(embodiment.physical_self.appearance)
    return AppearanceState(
        hairstyle=appearance.get("hairstyle", "canonical default"),
        hair_color=appearance.get("hair_hex", appearance.get("hair_color", "deep crimson")),
        tail_color=appearance.get("tail_hex", appearance.get("tail_color", "dark violet")),
        style_tags=("canonical", "engineer"),
    )


def presentation_state_path(state_path: str | Path) -> Path:
    state = Path(state_path)
    return state.parent / "avatar-presentation.json"


def load_or_bootstrap_presentation(
    *,
    embodiment: Embodiment,
    state_path: str | Path,
) -> PresentationRuntimeBundle:
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    store = PresentationStore(presentation_state_path(state_path))
    if store.exists():
        authority = store.load(catalog.wardrobe, outfits=outfits)
    else:
        authority = PresentationAuthority(
            catalog.wardrobe,
            outfits=outfits,
            canonical_daily_outfit_id="engineer.signature",
            initial_appearance=_appearance_from_embodiment(embodiment),
        )
        store.save(authority)
    return PresentationRuntimeBundle(authority, store, catalog)
