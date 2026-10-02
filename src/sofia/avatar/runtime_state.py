"""Bootstrap and persistence helpers for headless AVATAR presentation."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from sofia.embodiment.model import Embodiment

from .presentation import AppearanceState, PresentationAuthority
from .presentation_store import PresentationStore
from .wardrobe_catalog import WardrobePrebuild, build_starter_wardrobe
from .wardrobe_matrix import WardrobeSlotMatrix, build_wardrobe_matrix


@dataclass(frozen=True, slots=True)
class PresentationRuntimeBundle:
    authority: PresentationAuthority
    store: PresentationStore
    catalog: WardrobePrebuild

    def matrix_for(self, item_ids: tuple[str, ...]) -> WardrobeSlotMatrix:
        """Project one audience-safe garment selection into matrix state."""
        if not isinstance(item_ids, tuple) or any(
            not isinstance(item_id, str) for item_id in item_ids
        ):
            raise TypeError("item_ids must be a tuple of strings")
        return build_wardrobe_matrix(self.catalog, item_ids)

    def current_matrix(self) -> WardrobeSlotMatrix:
        """Project current authoritative presentation into slot/layer state."""
        return self.matrix_for(self.authority.current.item_ids)


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
    """Return the canonical SQLite database that owns AVATAR presentation."""
    return Path(state_path)


def legacy_presentation_state_path(state_path: str | Path) -> Path:
    state = Path(state_path)
    return state.parent / "avatar-presentation.json"


def _retired_legacy_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".migrated")
    index = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".migrated.{index}")
        index += 1
    return candidate


def _legacy_snapshot(path: Path) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "legacy AVATAR presentation state is unreadable"
        ) from exc
    if not isinstance(raw, dict):
        raise RuntimeError(
            "legacy AVATAR presentation state must be a JSON object"
        )
    return raw


def _migrate_legacy_presentation_state(
    *,
    store: PresentationStore,
    legacy_path: Path,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> None:
    if not legacy_path.is_file():
        return

    legacy_authority = PresentationAuthority.restore(
        wardrobe,
        outfits=outfits,
        snapshot=_legacy_snapshot(legacy_path),
    )
    if store.exists():
        canonical = store.load(wardrobe, outfits=outfits)
        if canonical.snapshot() != legacy_authority.snapshot():
            raise RuntimeError(
                "legacy avatar-presentation.json conflicts with canonical "
                "sofia.db; reconcile before startup"
            )
    else:
        store.save(legacy_authority)
        canonical = store.load(wardrobe, outfits=outfits)
        if canonical.snapshot() != legacy_authority.snapshot():
            raise RuntimeError(
                "legacy AVATAR presentation migration did not verify"
            )

    try:
        legacy_path.replace(_retired_legacy_path(legacy_path))
    except OSError as exc:
        raise RuntimeError(
            "legacy avatar-presentation.json was copied into canonical "
            "sofia.db but could not be retired"
        ) from exc


def load_or_bootstrap_presentation(
    *,
    embodiment: Embodiment,
    state_path: str | Path,
) -> PresentationRuntimeBundle:
    catalog = build_starter_wardrobe()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    store = PresentationStore(presentation_state_path(state_path))
    _migrate_legacy_presentation_state(
        store=store,
        legacy_path=legacy_presentation_state_path(state_path),
        wardrobe=catalog.wardrobe,
        outfits=outfits,
    )
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
