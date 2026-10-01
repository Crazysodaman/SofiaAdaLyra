"""Six distinct two-piece bikini designs for the AVATAR wardrobe catalog."""
from __future__ import annotations

from .wardrobe import Layer
from .wardrobe_piece_catalog import PieceSpec
from .wardrobe_routine import Activity, OutfitPlan, Season, Weather


_BIKINI_DESIGNS: tuple[
    tuple[str, str, str, str, str, str],
    ...,
] = (
    (
        "Cyberwave Triangle",
        "#0B0D12",
        "#19D3C5",
        "triangle-cut top with crisp teal edge piping",
        "mid-rise bottom with matching teal edge piping and a tail-clearance notch",
        "matte chlorine-resistant stretch swim knit",
    ),
    (
        "Violet Halter",
        "#3A245C",
        "#19D3C5",
        "halter-neck top with a softly curved neckline and teal clasp detail",
        "high-waist bottom with violet contour seams and a clean tail opening",
        "smooth violet swim jersey with resilient stretch",
    ),
    (
        "Crimson Sport",
        "#8B1E3F",
        "#171A21",
        "sport-style crossback top with charcoal support bands",
        "secure hipster-cut bottom with charcoal side panels and tail clearance",
        "structured performance swim knit",
    ),
    (
        "Midnight Asymmetric",
        "#171A21",
        "#3A245C",
        "one-shoulder top with a diagonal violet panel break",
        "asymmetric-waist bottom with a single violet side accent and tail clearance",
        "matte black swim fabric with satin-finish contrast panels",
    ),
    (
        "Teal Ring",
        "#19D3C5",
        "#0B0D12",
        "scoop-neck top with small dark ring connectors at the straps",
        "high-cut bottom with matching dark ring side details and tail clearance",
        "smooth teal stretch swim fabric with matte hardware",
    ),
    (
        "Crimson Violet Colorblock",
        "#5B2333",
        "#3A245C",
        "bandeau-style top with violet color blocking and removable-looking strap cues",
        "side-tie-style bottom with violet panels, compact knots, and tail clearance",
        "soft colorblocked swim knit with reinforced edge binding",
    ),
)


def generated_bikini_piece_specs() -> tuple[PieceSpec, ...]:
    """Return twelve garments that form six visually distinct bikini sets."""
    pieces: list[PieceSpec] = []
    for index, (
        label,
        primary,
        accent,
        top_detail,
        bottom_detail,
        material,
    ) in enumerate(_BIKINI_DESIGNS, start=1):
        key = f"{index:02d}"
        pieces.append(
            PieceSpec(
                item_id=f"closet.swim.bikini.{key}.top",
                name=f"{label} Bikini Top",
                description=(
                    f"{label} two-piece swimwear top in {primary} with {accent} "
                    f"accents; {top_detail}."
                ),
                category="closet.swim.bikini_top",
                layer=Layer.BASE,
                slots=("torso",),
                coverage=("torso",),
                primary_hex=primary,
                accent_hexes=(accent,),
                material=material,
                construction=(
                    f"Distinct bikini design {key}: {top_detail}.",
                    "Swimwear metadata only; no renderer asset is implied.",
                ),
                fit_anchors=("torso.front", "torso.back"),
                style_tags=("swimwear", "bikini", f"bikini-{key}", "top"),
                private_only=False,
            )
        )
        pieces.append(
            PieceSpec(
                item_id=f"closet.swim.bikini.{key}.bottom",
                name=f"{label} Bikini Bottom",
                description=(
                    f"{label} two-piece swimwear bottom in {primary} with {accent} "
                    f"accents; {bottom_detail}."
                ),
                category="closet.swim.bikini_bottom",
                layer=Layer.BASE,
                slots=("pelvis", "tail"),
                coverage=("pelvis",),
                primary_hex=primary,
                accent_hexes=(accent,),
                material=material,
                construction=(
                    f"Distinct bikini design {key}: {bottom_detail}.",
                    "Tail opening is part of the reviewed metadata design.",
                    "Swimwear metadata only; no renderer asset is implied.",
                ),
                fit_anchors=("pelvis.coverage", "tail.opening.clearance"),
                style_tags=("swimwear", "bikini", f"bikini-{key}", "bottom"),
                private_only=False,
                tail_clearance=True,
            )
        )
    return tuple(pieces)


def generated_bikini_outfits() -> tuple[OutfitPlan, ...]:
    """Return six complete bikini outfit templates."""
    return tuple(
        OutfitPlan(
            outfit_id=f"swim.bikini.{index:02d}",
            item_ids=(
                f"closet.swim.bikini.{index:02d}.top",
                f"closet.swim.bikini.{index:02d}.bottom",
            ),
            activities=frozenset({
                Activity.RELAXING,
                Activity.CONVERSATION,
            }),
            seasons=frozenset(Season),
            weather=frozenset({Weather.HOT, Weather.MILD}),
            style_tags=(
                "swimwear",
                "bikini",
                f"bikini-{index:02d}",
                "two-piece",
            ),
            display_name=_BIKINI_DESIGNS[index - 1][0] + " Bikini",
        )
        for index in range(1, 7)
    )
