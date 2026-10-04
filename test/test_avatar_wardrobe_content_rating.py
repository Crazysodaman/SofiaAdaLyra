"""Private/lewd/explicit wardrobe classification and creator support."""
import pytest

from sofia.avatar.authoring import GarmentDesignRequest, WardrobeStudio
from sofia.avatar.wardrobe import WardrobeError
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_design import (
    ContentRating,
    ExposureZone,
    GarmentDesign,
    GraphicDesign,
    validate_design,
)


def _request(**overrides):
    data = dict(
        item_id="studio.private.test",
        name="Private test bralette",
        garment_type="bralette",
        fit="fitted",
        rise=None,
        length="cropped",
        sleeve_length=None,
        material="soft stretch knit",
        primary="black",
        accent="dark_violet",
        pattern="solid",
        graphic=GraphicDesign(),
        features=(),
        description="A private test garment used for classification coverage.",
    )
    data.update(overrides)
    return GarmentDesignRequest(**data)


def test_creator_can_make_private_lewd_piece():
    studio = WardrobeStudio(build_starter_wardrobe())
    piece = studio.design_piece(
        _request(
            private_only=True,
            content_rating=ContentRating.LEWD,
        )
    )
    assert piece.private_only is True
    assert piece.content_rating is ContentRating.LEWD
    assert piece.exposure == ()


def test_creator_can_make_explicit_nipple_exposing_piece():
    studio = WardrobeStudio(build_starter_wardrobe())
    piece = studio.design_piece(
        _request(
            garment_type="open_cup_bra",
            private_only=True,
            content_rating=ContentRating.EXPLICIT,
            exposure=(ExposureZone.NIPPLES,),
        )
    )
    assert piece.garment.coverage == ()
    assert piece.exposure == (ExposureZone.NIPPLES,)


def test_creator_can_make_explicit_genital_exposing_piece():
    studio = WardrobeStudio(build_starter_wardrobe())
    piece = studio.design_piece(
        _request(
            garment_type="open_crotch_briefs",
            rise="mid",
            private_only=True,
            content_rating=ContentRating.EXPLICIT,
            exposure=(ExposureZone.GENITALS,),
        )
    )
    assert piece.garment.coverage == ()
    assert piece.exposure == (ExposureZone.GENITALS,)


@pytest.mark.parametrize("rating", [ContentRating.LEWD, ContentRating.EXPLICIT])
def test_lewd_or_explicit_piece_cannot_be_public(rating):
    with pytest.raises(WardrobeError, match="private-only"):
        GarmentDesign(
            item_id="bad.public.private",
            name="Invalid public private-content garment",
            garment_type="bralette",
            fit="fitted",
            rise=None,
            length="cropped",
            sleeve_length=None,
            material="soft stretch knit",
            primary="black",
            accent=None,
            pattern="solid",
            graphic=GraphicDesign(),
            features=(),
            content_rating=rating,
            description="Invalid test garment.",
        )


def test_exposure_requires_explicit_rating_and_noncovering_type():
    with pytest.raises(WardrobeError, match="explicit rating"):
        GarmentDesign(
            item_id="bad.exposure.rating",
            name="Invalid exposure rating",
            garment_type="open_cup_bra",
            fit="fitted",
            rise=None,
            length="cropped",
            sleeve_length=None,
            material="soft stretch knit",
            primary="black",
            accent=None,
            pattern="solid",
            graphic=GraphicDesign(),
            features=(),
            private_only=True,
            content_rating=ContentRating.LEWD,
            exposure=(ExposureZone.NIPPLES,),
            description="Invalid test garment.",
        )

    bad = GarmentDesign(
        item_id="bad.exposure.coverage",
        name="Invalid exposure coverage",
        garment_type="bralette",
        fit="fitted",
        rise=None,
        length="cropped",
        sleeve_length=None,
        material="soft stretch knit",
        primary="black",
        accent=None,
        pattern="solid",
        graphic=GraphicDesign(),
        features=(),
        private_only=True,
        content_rating=ContentRating.EXPLICIT,
        exposure=(ExposureZone.NIPPLES,),
        description="Invalid test garment.",
    )
    with pytest.raises(WardrobeError, match="cannot claim torso coverage"):
        validate_design(bad)
