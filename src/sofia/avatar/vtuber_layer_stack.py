"""Deterministic waist-up sprite stack built from the canonical wardrobe matrix.

This is a pure draw plan, NOT a renderer or permission issuer. It only returns
artwork verified by the existing asset bundle loader. No invented or guessed
sprites stand in for a missing garment. A protected plan may only be used
after the trusted UI revalidates the grant before painting the next frame.
"""
from __future__ import annotations

from dataclasses import dataclass

from .presentation import AttireMode, AudienceScope
from .vtuber_asset_bundle import (
    Avatar2DArtSelection, Avatar2DAssetError, Avatar2DSprite,
)
from .wardrobe import LEAF_SLOTS, Layer
from .wardrobe_matrix import WardrobeSlotMatrix


# Only slots that can plausibly enter the waist-up frame. An authored avatar
# may crop any of these; lower-body items remain owned by the wardrobe but
# need no visual sprite or click mask in this viewport.
WAIST_UP_SLOTS = frozenset({
    "torso", "back", "waist", "neck", "head", "hair", "tail",
    "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_upper_arm", "right_upper_arm",
    "left_forearm", "right_forearm",
    "left_wrist", "right_wrist",
    "left_hand", "right_hand",
    "left_fingers", "right_fingers",
})
assert WAIST_UP_SLOTS <= LEAF_SLOTS

_PHASES = {
    "base_back": 0,
    "base_body": 1000,
    "garment": 2000,
    "base_face": 8000,
    "base_front": 9000,
    "overlay": 10000,
}


@dataclass(frozen=True, slots=True)
class Avatar2DDrawLayer:
    sprite_id: str
    stack_order: int
    role: str
    garment_id: str | None
    # Canonical slot identifiers this *single real sprite* covers in the
    # current viewport, never guessed coordinates, geometry or pixels.
    visible_slots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Avatar2DLayerStack:
    presentation_revision: int
    bundle_digest: str
    audience: AudienceScope
    attire: AttireMode
    outfit_id: str | None
    draw_layers: tuple[Avatar2DDrawLayer, ...]


def assemble_avatar2d_layers(
    selection: Avatar2DArtSelection,
    *,
    matrix: WardrobeSlotMatrix | None,
) -> Avatar2DLayerStack:
    """Validate a complete real sprite set against authoritative garment slots.

    - Public requires a covered public matrix and no private garments.
    - Private dressed views require the matching current matrix.
    - Nude has no garment selection and cannot accept any garment sprites.
    - Every *visible* occupied wardrobe cell needs at least one matching
      rendered sprite. Cropped pelvis/legs need no layers in waist-up view.
    - The base face/hair are independent of garment swaps.
    """
    if not isinstance(selection, Avatar2DArtSelection):
        raise TypeError("verified avatar artwork selection required")
    bundle = selection.bundle
    projection = selection.projection
    if bundle is None or bundle._closed:
        raise Avatar2DAssetError("verified avatar artwork is unavailable")
    if selection.status == "private":
        if (
            projection.audience is not AudienceScope.PRIVATE
            or projection.private_fallback_used
            or bundle.audience is not AudienceScope.PRIVATE
        ):
            raise Avatar2DAssetError("private artwork scope mismatch")
    elif selection.status in ("public", "public_fallback"):
        if (
            bundle.audience is not AudienceScope.PUBLIC
            or projection.audience is not AudienceScope.PUBLIC
        ):
            raise Avatar2DAssetError("public artwork scope mismatch")
    else:
        raise Avatar2DAssetError("artwork selection not renderable")
    if (
        bundle.attire is not projection.attire
        or bundle.outfit_id != projection.outfit_id
        or (bundle.audience is AudienceScope.PRIVATE and
            selection.status != "private")
    ):
        raise Avatar2DAssetError("current appearance and artwork mismatch")

    if projection.attire is AttireMode.NUDE:
        if selection.status != "private":
            raise Avatar2DAssetError("nude rendering requires authorized private selection")
        if projection.item_ids or matrix is not None and matrix.item_ids:
            raise Avatar2DAssetError("nude view cannot contain wardrobe garments")
        garments: dict[tuple[str, Layer, str], bool] = {}
    else:
        if not isinstance(matrix, WardrobeSlotMatrix):
            raise Avatar2DAssetError("dressed avatar requires existing wardrobe matrix")
        if matrix.item_ids != projection.item_ids:
            raise Avatar2DAssetError("wardrobe matrix does not match presentation")
        if selection.status != "private" and (
            not matrix.covered_default or matrix.private_only
        ):
            raise Avatar2DAssetError("public avatar requires covered safe outfit")
        if selection.status == "private" and not matrix.private_only:
            raise Avatar2DAssetError("private dressed view needs private wardrobe")
        garments = {
            (cell.garment_id, cell.layer, cell.slot): False
            for cell in matrix.cells if cell.slot in WAIST_UP_SLOTS
        }

    if not bundle.sprites:
        raise Avatar2DAssetError("art bundle has no sprite layer bindings")
    drawn: list[Avatar2DDrawLayer] = []
    base_body = False
    for sprite in bundle.sprites:
        if not isinstance(sprite, Avatar2DSprite):
            raise Avatar2DAssetError("invalid verified sprite descriptor")
        if sprite.sprite_id not in bundle.images:
            raise Avatar2DAssetError("verified sprite has no image data")
        if sprite.role not in _PHASES:
            raise Avatar2DAssetError("unknown sprite compositing role")
        if sprite.role == "base_body":
            base_body = True
        if sprite.role == "garment":
            if projection.attire is AttireMode.NUDE or sprite.wardrobe_layer is None:
                raise Avatar2DAssetError("invalid garment in selected attire")
            covered_slots = []
            for slot in sprite.slots:
                if slot not in WAIST_UP_SLOTS:
                    raise Avatar2DAssetError("garment sprite targets outside waist-up view")
                key = (sprite.garment_id, sprite.wardrobe_layer, slot)
                if key not in garments:
                    raise Avatar2DAssetError("sprite does not match canonical garment slot")
                garments[key] = True
                covered_slots.append(slot)
            order = _PHASES["garment"] + int(sprite.wardrobe_layer) * 100 + sprite.order
        else:
            if sprite.garment_id is not None or sprite.slots or sprite.wardrobe_layer is not None:
                raise Avatar2DAssetError("non-garment sprite forged a wardrobe slot")
            covered_slots = []
            order = _PHASES[sprite.role] + sprite.order
        drawn.append(
            Avatar2DDrawLayer(
                sprite_id=sprite.sprite_id,
                stack_order=order,
                role=sprite.role,
                garment_id=sprite.garment_id,
                visible_slots=tuple(covered_slots),
            )
        )
    if not base_body:
        raise Avatar2DAssetError("canonical base sprite is missing")
    if not all(garments.values()):
        raise Avatar2DAssetError("visible garment sprite is missing")
    if (
        projection.attire is AttireMode.CLOTHED
        and "torso" not in {slot for garment, layer, slot in garments}
    ):
        raise Avatar2DAssetError("rendered outfit has no torso coverage")
    drawn.sort(key=lambda item: (item.stack_order, item.sprite_id))
    return Avatar2DLayerStack(
        presentation_revision=projection.source_revision,
        bundle_digest=bundle.digest,
        audience=bundle.audience,
        attire=projection.attire,
        outfit_id=projection.outfit_id,
        draw_layers=tuple(drawn),
    )
