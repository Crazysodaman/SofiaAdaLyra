"""Generated seasonal outfit presets assembled from individual closet pieces.

There are 25 normal, 25 lounge and 25 adult/private outfits for each season.
Private outfits are metadata-only and remain outside automatic public selection.
"""
from __future__ import annotations

from .wardrobe_routine import Activity, OutfitPlan, Season


def _n(kind: str, index: int) -> str:
    return f"closet.normal.{kind}.{index:02d}"


def _p(kind: str, index: int) -> str:
    return f"closet.private.{kind}.{index:02d}"


def _seasonal_normal(season: Season, index: int) -> OutfitPlan:
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", index),
        _n("bottom", ((index + season.value.__len__() - 1) % 25) + 1),
        _n("footwear", ((index + 3) % 25) + 1),
        _n("neckwear", ((index + 7) % 25) + 1),
    )
    if season in {Season.SPRING, Season.AUTUMN, Season.WINTER}:
        items += (_n("outerwear", ((index + 11) % 25) + 1),)
    return OutfitPlan(
        f"seasonal.{season.value}.normal.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.FORMAL}),
        frozenset({season}),
        style_tags=("seasonal", "normal", season.value),
        display_name=f"{season.value.title()} Everyday {index:02d}",
    )


def _seasonal_lounge(season: Season, index: int) -> OutfitPlan:
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", ((index + 4) % 25) + 1),
        _n("bottom", ((index + 9) % 25) + 1),
        _n("hair_accessory", ((index + 13) % 25) + 1),
    )
    if season is Season.WINTER:
        items += (_n("legwear", ((index + 2) % 25) + 1),)
    return OutfitPlan(
        f"seasonal.{season.value}.lounge.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.RELAXING, Activity.SLEEP}),
        frozenset({season}),
        lounge=True,
        style_tags=("seasonal", "lounge", "cozy", "soft", season.value),
        display_name=f"{season.value.title()} Lounge {index:02d}",
    )


def _seasonal_private(season: Season, index: int) -> OutfitPlan:
    items = (
        _p("bra", index),
        _p("panty", ((index + 5) % 25) + 1),
        _p("legwear", ((index + 10) % 25) + 1),
        _p("neckwear", ((index + 15) % 25) + 1),
        _p("footwear", ((index + 20) % 25) + 1),
    )
    return OutfitPlan(
        f"seasonal.{season.value}.private.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.RELAXING}),
        frozenset({season}),
        private_only=True,
        style_tags=("seasonal", "adult-private", "intimate-style", season.value),
        display_name=f"{season.value.title()} Private {index:02d}",
    )


def generated_seasonal_outfits() -> tuple[OutfitPlan, ...]:
    outfits: list[OutfitPlan] = []
    for season in Season:
        for index in range(1, 26):
            outfits.append(_seasonal_normal(season, index))
            outfits.append(_seasonal_lounge(season, index))
            outfits.append(_seasonal_private(season, index))
    return tuple(outfits)
