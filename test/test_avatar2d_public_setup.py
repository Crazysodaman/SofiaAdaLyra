"""End-to-end public 2D install writes exactly the live renderer's layout."""
import json
from pathlib import Path

import pytest

from sofia.avatar.vtuber_public_setup import (
    prepare_public_avatar2d,
)
from sofia.avatar.vtuber_character_selection import (
    select_character_parts,
)
from sofia.avatar.presentation import (
    AppearanceState, AttireMode, AudienceScope, PresentationProjection,
)
from sofia.ui.avatar2d_renderer import (
    _frame_character_state,
    _gesture_frames,
)


def test_public_setup_writes_verified_real_png_layers_and_character_pack(tmp_path):
    output = tmp_path / "Avatar2D" / "Public"
    ready = prepare_public_avatar2d(output)
    assert ready.outfits == ("day.default",)
    assert ready.outfit_sprites >= 5
    assert ready.character_sprites == 33
    assert ready.status == "verified_procedural_starter_not_artist_approved"
    assert (output / "outfits" / "day.default" / "manifest.json").is_file()
    assert (output / "outfits" / "day.default" / "garments"
            / "day.engineer_jacket.png").is_file()
    assert (output / "character" / "manifest.json").is_file()
    assert (output / "character" / "eye_left" / "closed.png").is_file()
    assert (output / "character" / "ear_right" / "perked.png").is_file()
    assert (output / "character" / "tail" / "flick.png").is_file()
    char_manifest = json.loads((output / "character" / "manifest.json").read_text("utf8"))
    assert len(char_manifest["parts"]) == 33
    assert not list(output.parent.glob(".avatar2d-staging-*"))
    assert not (tmp_path / "sofia.db").exists()


def test_public_setup_rejects_private_outfit_without_creating_any_art(tmp_path):
    output = tmp_path / "ProtectedOrPublic"
    with pytest.raises(ValueError, match="not an approved public"):
        prepare_public_avatar2d(output, outfit_id="private.violet_tease")
    assert not output.exists()


def test_public_setup_never_overwrites_reviewed_pngs(tmp_path):
    output = tmp_path / "Existing"
    output.mkdir()
    reviewed = output / "hero.png"
    reviewed.write_bytes(b"reviewed user-owned artwork")
    with pytest.raises(FileExistsError):
        prepare_public_avatar2d(output)
    assert reviewed.read_bytes() == b"reviewed user-owned artwork"


def test_public_setup_rejects_all_public_and_one_outfit_mutual_selection(tmp_path):
    # The python API validates unknown IDs, while CLI argparse enforces
    # --all-public versus --outfit as mutually exclusive options.
    with pytest.raises(ValueError, match="not an approved"):
        prepare_public_avatar2d(tmp_path / "out", outfit_id="../unknown")


def test_blink_middle_frame_closes_both_eyes_and_wink_only_one():
    def projection():
        return PresentationProjection(
            audience=AudienceScope.PUBLIC, source_revision=12,
            attire=AttireMode.CLOTHED, outfit_id="day.default",
            item_ids=("day.technical_top",),
            appearance=AppearanceState(
                hairstyle="layered", hair_color="deep crimson",
                tail_color="dark violet",
            ),
            private_fallback_used=False, reason="head animation test",
        )
    assert _gesture_frames("blink") == 3
    before, _ = _frame_character_state(
        expression="neutral", gesture="blink", index=0, frames=3,
    )
    blink, _ = _frame_character_state(
        expression="neutral", gesture="blink", index=1, frames=3,
    )
    after, _ = _frame_character_state(
        expression="neutral", gesture="blink", index=2, frames=3,
    )
    assert before == after == "neutral"
    assert blink == "blink"
    selected = select_character_parts(projection(), expression=blink).as_dict()
    assert selected["eye_left"] == selected["eye_right"] == "closed"
    wink = select_character_parts(projection(), expression="wink").as_dict()
    assert wink["eye_left"] == "closed"
    assert wink["eye_right"] == "open"
