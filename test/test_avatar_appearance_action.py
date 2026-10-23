"""Production route for owner-authorized reversible avatar styling."""
from __future__ import annotations

from pathlib import Path

import pytest

from sofia.avatar.clothing_action import ClothingActionService
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.core.embodiment.store import EmbodimentStore


SEED = Path(__file__).resolve().parents[1] / "src/sofia/core/embodiment/avatar.json"


def create_service(tmp_path):
    bundle = load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path / "sofia.db",
    )
    return ClothingActionService(bundle), bundle


def action(service, content, revision):
    return service.handle(
        content=content,
        previous_user_content=None,
        operation_id=f"owner.look.{revision}",
    )


def test_real_handler_changes_eyes_hair_and_posture_with_durable_receipts(tmp_path):
    service, bundle = create_service(tmp_path)
    assert "revision 2" in action(service, "change your eye color to blue", 2)
    assert "revision 3" in action(service, "change your hair color to violet", 3)
    assert "revision 4" in action(service, "set your posture to hip-pop", 4)
    assert bundle.authority.current.appearance.eye_color == "#4169E1"
    assert bundle.authority.current.appearance.hair_color == "#8F5BDB"
    assert bundle.authority.current.appearance.posture == "hip-pop"
    assert bundle.store.load(
        bundle.catalog.wardrobe,
        outfits={p.outfit_id: p.item_ids for p in bundle.catalog.presets},
    ).current.appearance.eye_color == "#4169E1"


def test_tattoos_and_piercings_are_reversible_and_favoritable(tmp_path):
    service, bundle = create_service(tmp_path)
    action(service, "add a tattoo of fox silhouette", 2)
    action(service, "add a piercing of silver ear stud", 3)
    look = bundle.authority.current.appearance
    assert look.tattoos == ("fox silhouette",)
    assert look.piercings == ("silver ear stud",)
    assert "saved" in action(service, "save this look as weekend", 4)
    action(service, "remove your tattoos", 5)
    assert bundle.authority.current.appearance.tattoos == ()
    assert "revision 5" in action(service, "use favorite look weekend", 6)
    assert bundle.authority.current.appearance == look
    assert bundle.store.list_style_favorites()["weekend"] == look


@pytest.mark.parametrize("command", (
    "change your face shape to square",
    "change your number of tails to nine",
    "change your number of ears to four",
    "change your limb count to six",
    "change your species to human",
))
def test_no_unreviewed_mutation_of_permanent_anatomy(tmp_path, command):
    service, bundle = create_service(tmp_path)
    first = bundle.authority.current.revision
    assert action(service, command, 2) is None
    assert bundle.authority.current.revision == first
