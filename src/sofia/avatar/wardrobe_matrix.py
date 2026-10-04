"""Authoritative slot/layer projection for AVATAR wardrobe state.

The matrix is derived from validated wardrobe metadata plus the authoritative
presentation item IDs. It does not invent renderer geometry or claim a visual
asset exists. Every known AVATAR slot and every clothing layer is represented,
including empty cells. Broad authoring slots are expanded into left/right leaf slots so partial changes can be reasoned about deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .wardrobe import LEAF_SLOTS, Layer, WardrobeError, normalize_slots

if TYPE_CHECKING:
    from .wardrobe_catalog import WardrobePrebuild


@dataclass(frozen=True, slots=True)
class WardrobeMatrixCell:
    slot: str
    layer: Layer
    garment_id: str
    name: str
    description: str
    category: str
    primary_hex: str
    accent_hexes: tuple[str, ...]
    style_tags: tuple[str, ...]
    design_signature: str
    private_only: bool
    content_rating: str
    exposure: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WardrobeSlotMatrix:
    item_ids: tuple[str, ...]
    cells: tuple[WardrobeMatrixCell, ...]
    coverage: frozenset[str]
    covered_default: bool
    private_only: bool

    def cell(
        self,
        *,
        slot: str,
        layer: Layer,
    ) -> WardrobeMatrixCell | None:
        if slot not in LEAF_SLOTS:
            raise WardrobeError("unknown wardrobe matrix leaf slot")
        if not isinstance(layer, Layer):
            raise WardrobeError("unknown wardrobe matrix layer")
        return next(
            (
                cell
                for cell in self.cells
                if cell.slot == slot and cell.layer is layer
            ),
            None,
        )

    def as_dict(self) -> dict[str, dict[str, dict[str, object] | None]]:
        """Return every slot x layer cell, including explicit empty cells."""
        occupied = {
            (cell.slot, cell.layer): cell
            for cell in self.cells
        }
        return {
            slot: {
                layer.name.lower(): (
                    None
                    if (cell := occupied.get((slot, layer))) is None
                    else {
                        "garment_id": cell.garment_id,
                        "name": cell.name,
                        "description": cell.description,
                        "category": cell.category,
                        "primary_hex": cell.primary_hex,
                        "accent_hexes": list(cell.accent_hexes),
                        "style_tags": list(cell.style_tags),
                        "design_signature": cell.design_signature,
                        "private_only": cell.private_only,
                        "content_rating": cell.content_rating,
                        "exposure": list(cell.exposure),
                    }
                )
                for layer in Layer
            }
            for slot in sorted(LEAF_SLOTS)
        }


def build_wardrobe_matrix(
    catalog: "WardrobePrebuild",
    item_ids: tuple[str, ...],
) -> WardrobeSlotMatrix:
    """Project a validated outfit selection into all authoritative matrix cells."""
    from .wardrobe_catalog import WardrobePrebuild

    if not isinstance(catalog, WardrobePrebuild):
        raise TypeError("catalog must be WardrobePrebuild")

    selection = catalog.wardrobe.selection(item_ids)
    blueprints = {
        blueprint.garment.item_id: blueprint
        for blueprint in catalog.blueprints
    }
    cells: list[WardrobeMatrixCell] = []
    for garment in catalog.wardrobe.garments(item_ids):
        try:
            blueprint = blueprints[garment.item_id]
        except KeyError as exc:
            raise WardrobeError(
                "matrix garment is missing authoritative blueprint metadata"
            ) from exc
        for slot in normalize_slots(garment.slots):
            cells.append(
                WardrobeMatrixCell(
                    slot=slot,
                    layer=garment.layer,
                    garment_id=garment.item_id,
                    name=garment.name,
                    description=blueprint.description,
                    category=blueprint.category,
                    primary_hex=blueprint.primary_hex,
                    accent_hexes=blueprint.accent_hexes,
                    style_tags=blueprint.style_tags,
                    design_signature=blueprint.design_signature,
                    private_only=blueprint.private_only,
                    content_rating=blueprint.content_rating.value,
                    exposure=tuple(zone.value for zone in blueprint.exposure),
                )
            )

    return WardrobeSlotMatrix(
        item_ids=selection.item_ids,
        cells=tuple(cells),
        coverage=frozenset(normalize_slots(selection.coverage)),
        covered_default=selection.covered_default,
        private_only=selection.private_only,
    )
