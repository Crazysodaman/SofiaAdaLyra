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
        hair_color=appearance.get("hair_color", appearance.get("hair_hex", "deep crimson")),
        tail_color=appearance.get("tail_color", appearance.get("tail_hex", "dark violet")),
        style_tags=("canonical", "engineer"),
    )


def _migrate_legacy_bootstrap_colors(
    *,
    authority: PresentationAuthority,
    embodiment: Embodiment,
    store: PresentationStore,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> PresentationAuthority:
    """Normalize only the original headless bootstrap color encoding.

    Early headless AVATAR builds stored canonical hex values in the semantic
    hair_color/tail_color fields. Migrate only the untouched revision-1
    canonical bootstrap state so deliberate later appearance changes are
    never rewritten.
    """
    current = authority.current
    daily = authority.last_daily
    if (
        current.revision != 1
        or daily.revision != 1
        or current.reason != "canonical_daily_bootstrap"
        or daily.reason != "canonical_daily_bootstrap"
        or current.outfit_id != "engineer.signature"
        or daily.outfit_id != "engineer.signature"
        or current.private_only
        or daily.private_only
    ):
        return authority

    canonical = dict(embodiment.physical_self.appearance)
    hair_hex = canonical.get("hair_hex")
    tail_hex = canonical.get("tail_hex")
    hair_name = canonical.get("hair_color")
    tail_name = canonical.get("tail_color")
    if (
        not isinstance(hair_name, str)
        or not isinstance(tail_name, str)
        or current.appearance.hair_color != hair_hex
        or current.appearance.tail_color != tail_hex
        or daily.appearance.hair_color != hair_hex
        or daily.appearance.tail_color != tail_hex
    ):
        return authority

    migrated = PresentationAuthority(
        wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id="engineer.signature",
        initial_appearance=AppearanceState(
            hairstyle=current.appearance.hairstyle,
            hair_color=hair_name,
            tail_color=tail_name,
            style_tags=current.appearance.style_tags,
        ),
    )
    store.save(migrated)
    return migrated


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
        authority = _migrate_legacy_bootstrap_colors(
            authority=authority,
            embodiment=embodiment,
            store=store,
            wardrobe=catalog.wardrobe,
            outfits=outfits,
        )
    else:
        authority = PresentationAuthority(
            catalog.wardrobe,
            outfits=outfits,
            canonical_daily_outfit_id="engineer.signature",
            initial_appearance=_appearance_from_embodiment(embodiment),
        )
        store.save(authority)
    return PresentationRuntimeBundle(authority, store, catalog)
