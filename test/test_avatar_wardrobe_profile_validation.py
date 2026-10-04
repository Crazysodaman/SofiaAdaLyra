"""Nested garment profiles fail closed on invalid runtime values."""
import pytest

from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_design import (
    ComfortProfile,
    ContextProfile,
    HumidityProfile,
    MovementProfile,
    SunlightProfile,
    WindProfile,
)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: HumidityProfile(low="good"),
        lambda: WindProfile(resistance="high"),
        lambda: SunlightProfile(direct_sun="good"),
        lambda: MovementProfile(mobility="excellent"),
        lambda: ContextProfile(dayparts="night"),
        lambda: ComfortProfile(softness="high"),
    ],
)
def test_nested_profiles_reject_untyped_values(factory):
    with pytest.raises(WardrobeError):
        factory()
