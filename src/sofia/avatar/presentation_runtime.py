"""Runtime bootstrap and migration for headless AVATAR presentation."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from sofia.embodiment.model import Embodiment

from .presentation import AppearanceState, PresentationAuthority
from .presentation_store import PresentationStore, PresentationStoreError
from .wardrobe_prebuild import DAY_DEFAULT_OUTFIT_ID, WardrobePrebuild
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


def _authority_from_obsolete_snapshot(
    *,
    snapshot: dict[str, object],
    embodiment: Embodiment,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> PresentationAuthority | None:
    """Convert a recognized pre-v2 wardrobe snapshot to the new catalog."""
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
    if not isinstance(appearance_data, dict):
        return None

    normalized_appearance = dict(appearance_data)
    canonical_appearance = dict(embodiment.physical_self.appearance)
    hair_hex = canonical_appearance.get("hair_hex")
    tail_hex = canonical_appearance.get("tail_hex")
    hair_name = canonical_appearance.get("hair_color")
    tail_name = canonical_appearance.get("tail_color")
    if (
        isinstance(hair_name, str)
        and normalized_appearance.get("hair_color") == hair_hex
    ):
        normalized_appearance["hair_color"] = hair_name
    if (
        isinstance(tail_name, str)
        and normalized_appearance.get("tail_color") == tail_hex
    ):
        normalized_appearance["tail_color"] = tail_name

    appearance = PresentationAuthority._appearance_from_dict(
        normalized_appearance
    )
    authority = PresentationAuthority(
        wardrobe,
        outfits=outfits,
        canonical_daily_outfit_id=DAY_DEFAULT_OUTFIT_ID,
        initial_appearance=appearance,
    )

    finished = snapshot.get("finished", [])
    if isinstance(finished, list):
        migrated_snapshot = authority.snapshot()
        migrated_snapshot["finished"] = finished
        authority = PresentationAuthority.restore(
            wardrobe,
            outfits=outfits,
            snapshot=migrated_snapshot,
        )
    return authority


def _migrate_obsolete_wardrobe_snapshot(
    *,
    store: PresentationStore,
    embodiment: Embodiment,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> PresentationAuthority | None:
    raw = store._read_snapshot_json()
    if raw is None:
        return None
    try:
        snapshot = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(snapshot, dict):
        return None

    authority = _authority_from_obsolete_snapshot(
        snapshot=snapshot,
        embodiment=embodiment,
        wardrobe=wardrobe,
        outfits=outfits,
    )
    if authority is not None:
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
    embodiment: Embodiment,
    wardrobe,
    outfits: dict[str, tuple[str, ...]],
) -> None:
    if not legacy_path.is_file():
        return

    snapshot = _legacy_snapshot(legacy_path)
    try:
        legacy_authority = PresentationAuthority.restore(
            wardrobe,
            outfits=outfits,
            snapshot=snapshot,
        )
    except Exception:
        legacy_authority = _authority_from_obsolete_snapshot(
            snapshot=snapshot,
            embodiment=embodiment,
            wardrobe=wardrobe,
            outfits=outfits,
        )
        if legacy_authority is None:
            raise
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
    from .wardrobe_review import WardrobeReviewStore
    catalog = WardrobeReviewStore(state_path).catalog()
    outfits = {plan.outfit_id: plan.item_ids for plan in catalog.presets}
    store = PresentationStore(Path(state_path))
    _migrate_legacy_presentation_state(
        store=store,
        legacy_path=_legacy_presentation_state_path(state_path),
        embodiment=embodiment,
        wardrobe=catalog.wardrobe,
        outfits=outfits,
    )
    if store.exists():
        try:
            authority = store.load(catalog.wardrobe, outfits=outfits)
        except PresentationStoreError:
            authority = _migrate_obsolete_wardrobe_snapshot(
                store=store,
                embodiment=embodiment,
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
    from sofia.config.user_settings import RuntimeUserSettingsStore
    from uuid import uuid4
    selected = RuntimeUserSettingsStore(state_path).load().avatar_daily_outfit
    if selected is not None and authority.last_daily.outfit_id != selected:
        def apply_daily_outfit():
            operation_id = f"settings-{uuid4()}"
            authority.propose_outfit(
                operation_id=operation_id, expected_revision=authority.current.revision,
                outfit_id=selected, reason="Owner-selected daily outfit",
            )
            return authority.commit_text(operation_id=operation_id, renderer_unavailable=True)
        store.persist_mutation(authority, apply_daily_outfit)
    return PresentationRuntimeBundle(authority, store, catalog)
