"""Runtime bootstrap and migration for headless AVATAR presentation."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from sofia.embodiment.model import Embodiment

from .presentation import AppearanceState, PresentationAuthority
from .presentation_store import PresentationStore, PresentationStoreError
from .wardrobe_catalog import (
    DAY_DEFAULT_OUTFIT_ID,
    WardrobePrebuild,
    build_starter_wardrobe,
)
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


def _migrate_obsolete_wardrobe_snapshot(
    *,
    store: PresentationStore,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> PresentationAuthority | None:
    """Reset recognized pre-v2 wardrobe state onto the new starter closet."""
    raw = store._read_snapshot_json()
    if raw is None:
        return None
    try:
        snapshot = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(snapshot, dict):
        return None
    canonical = snapshot.get("canonical_daily_outfit_id")
    current = snapshot.get("current")
    daily = snapshot.get("last_daily")
    if not isinstance(current, dict) or not isinstance(daily, dict):
        return None
    ids = (canonical, current.get("outfit_id"), daily.get("outfit_id"))
    legacy_exact = {
        "engineer.signature",
        "engineer.light",
        "lounge.relaxed",
        "lounge.graphic",
    }
    recognized = any(value in legacy_exact for value in ids)
    recognized = recognized or any(
        isinstance(value, str)
        and (
            value.startswith("seasonal.")
            or value.startswith("swim.bikini.")
            or value.startswith("dynamic.")
        )
        for value in ids
    )
    if not recognized:
        return None

    appearance_data = current.get("appearance")
    if not isinstance(appearance_data, dict):
        appearance_data = daily.get("appearance")
    appearance = PresentationAuthority._appearance_from_dict(appearance_data)
    authority = PresentationAuthority(
        wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id=DAY_DEFAULT_OUTFIT_ID,
        initial_appearance=appearance,
    )
    store.save(authority)
    return authority

def _legacy_presentation_state_path(state_path: str | Path) -> Path:
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
    store = PresentationStore(Path(state_path))
    _migrate_legacy_presentation_state(
        store=store,
        legacy_path=_legacy_presentation_state_path(state_path),
        wardrobe=catalog.wardrobe,
        outfits=outfits,
    )
    if store.exists():
        try:
            authority = store.load(catalog.wardrobe, outfits=outfits)
        except PresentationStoreError:
            authority = _migrate_obsolete_wardrobe_snapshot(
                store=store,
                wardrobe=catalog.wardrobe,
                outfits=outfits,
            )
            if authority is None:
                raise
    else:
        authority = PresentationAuthority(
            catalog.wardrobe,
            outfits=outfits,
            canonical_daily_outfit_id=DAY_DEFAULT_OUTFIT_ID,
            initial_appearance=_appearance_from_embodiment(embodiment),
        )
        store.save(authority)
    return PresentationRuntimeBundle(authority, store, catalog)
