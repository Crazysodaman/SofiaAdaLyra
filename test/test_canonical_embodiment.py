import json
from pathlib import Path

from sofia.embodiment.model import (
    ClothingItem,
    ClothingSpecification,
)
from sofia.embodiment.store import AvatarStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_AVATAR = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "data"
    / "avatar.json"
)


def test_canonical_avatar_contains_clothing_specification():
    data = json.loads(
        CANONICAL_AVATAR.read_text(
            encoding="utf-8-sig"
        )
    )

    clothing = data["clothing"]

    assert (
        clothing["canonical_status"]
        == "CANON: Sofía Clothing Technical Specification v1.0"
    )

    categories = {
        item["category"]
        for item in clothing["items"]
    }

    assert "Design philosophy" in categories
    assert "Engineer jacket" in categories
    assert "Trousers" in categories
    assert "Boots" in categories
    assert "Tail integration" in categories
    assert "Clothing design rule" in categories


def test_clothing_specification_is_immutable():
    clothing = ClothingSpecification(
        items=(
            ClothingItem(
                category="Boots",
                specification="Engineer boots",
            ),
        ),
        canonical_status="CANON",
    )

    try:
        clothing.items = ()
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "ClothingSpecification must be immutable."
        )


def test_canonical_avatar_round_trips_clothing():
    store = AvatarStore(CANONICAL_AVATAR)

    embodiment = store.load()

    assert (
        embodiment.clothing.canonical_status
        == "CANON: Sofía Clothing Technical Specification v1.0"
    )

    clothing = dict(
        (
            item.category,
            item.specification,
        )
        for item in embodiment.clothing.items
    )

    assert (
        clothing["Engineer jacket"]
        == "Signature fitted asymmetrical cyberpunk utility jacket"
    )

    assert (
        clothing["Jacket dimensions"]
        == '~16" shoulder width, ~25" length, ~24.5" sleeve length'
    )

    assert (
        clothing["Tail integration"]
        == "Tail emerges naturally from rear hip/pelvis region; unrestricted movement; no compression beneath belt or clothing"
    )

    assert (
        clothing["Clothing design rule"]
        == "Everything should look like it has a job."
    )