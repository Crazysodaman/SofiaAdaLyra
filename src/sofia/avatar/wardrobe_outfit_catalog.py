"""Generated seasonal outfit presets assembled from individual closet pieces.

There are 25 normal, 25 lounge and 25 adult/private outfits for each season.
Private outfits are metadata-only and remain outside automatic public selection.
"""
from __future__ import annotations

from .wardrobe_routine import Activity, OutfitPlan, Season


_SEASON_INDEX = {
    Season.SPRING: 0,
    Season.SUMMER: 1,
    Season.AUTUMN: 2,
    Season.WINTER: 3,
}


def _shift(index: int, offset: int) -> int:
    return ((index - 1 + offset) % 25) + 1


def _n(kind: str, index: int) -> str:
    return f"closet.normal.{kind}.{index:02d}"


def _p(kind: str, index: int) -> str:
    return f"closet.private.{kind}.{index:02d}"


def _seasonal_normal(season: Season, index: int) -> OutfitPlan:
    season_index = _SEASON_INDEX[season]
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", index),
        _n("bottom", _shift(index, 2 + season_index * 3)),
        _n("footwear", _shift(index, 4 + season_index * 5)),
        _n("neckwear", _shift(index, 8 + season_index * 7)),
    )
    if season in {Season.SPRING, Season.AUTUMN, Season.WINTER}:
        items += (
            _n(
                "outerwear",
                _shift(index, 12 + season_index * 11),
            ),
        )
    return OutfitPlan(
        f"seasonal.{season.value}.normal.{index:02d}",
        items,
        frozenset({Activity.CONVERSATION, Activity.FORMAL}),
        frozenset({season}),
        style_tags=("seasonal", "normal", season.value),
        display_name=f"{season.value.title()} Everyday {index:02d}",
    )


def _seasonal_lounge(season: Season, index: int) -> OutfitPlan:
    season_index = _SEASON_INDEX[season]
    items = (
        "underlayer.top",
        "underlayer.bottom",
        _n("top", _shift(index, 4)),
        _n("bottom", _shift(index, 9 + season_index * 3)),
        _n(
            "hair_accessory",
            _shift(index, 13 + season_index * 5),
        ),
    )
    if season is Season.WINTER:
        items += (_n("legwear", _shift(index, 2)),)
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
    season_index = _SEASON_INDEX[season]
    items = (
        _p("bra", index),
        _p("panty", _shift(index, 5 + season_index * 3)),
        _p("legwear", _shift(index, 10 + season_index * 5)),
        _p("neckwear", _shift(index, 15 + season_index * 7)),
        _p("footwear", _shift(index, 20 + season_index * 9)),
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
