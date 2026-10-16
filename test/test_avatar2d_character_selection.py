"""Face/fox options are derived, bounded and audience safe."""
from dataclasses import replace
from pathlib import Path

import pytest

from sofia.avatar.presentation import AudienceScope
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.vtuber_character_selection import select_character_parts
from sofia.embodiment.store import EmbodimentStore


SEED=Path(__file__).resolve().parents[1]/"src/sofia/embodiment/avatar.json"


def projection(tmp_path):
    rt=load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path/"sofia.db",
    )
    return rt.authority.projection(AudienceScope.PUBLIC)


def test_current_appearance_has_canonical_long_crimson_hair_and_fox_parts(tmp_path):
    output=select_character_parts(projection(tmp_path))
    groups=output.as_dict()
    assert groups["face"]=="neutral"
    assert groups["eye_left"]=="open"
    assert groups["eye_right"]=="open"
    assert groups["mouth"]=="closed"
    assert groups["hair_back"]==groups["hair_front"]=="long_layered"
    assert groups["ear_left"]==groups["ear_right"]=="perked"
    assert groups["tail"]=="calm"


def test_expression_ear_tail_and_real_audio_state_select_written_sprite_ids(tmp_path):
    projection_=projection(tmp_path)
    amended=replace(
        projection_,
        appearance=replace(projection_.appearance,
                           hairstyle="tied-back",
                           tail_pose="raised"),
    )
    chosen=select_character_parts(
        amended,expression="skeptical",gesture="ear-flick",
        talking=True,gaze="left",optional_freckles=True,
    ).as_dict()
    assert chosen["hair_front"]=="tied_back"
    assert chosen["brow_left"]=="skeptical"
    assert chosen["brow_right"]=="neutral"
    assert chosen["eye_left"]=="looking_left"
    assert chosen["eye_right"]=="looking_left"
    assert chosen["mouth"]=="talk_small"
    assert chosen["ear_left"]=="perked"
    assert chosen["tail"]=="raised"
    assert chosen["freckles"]=="on"


def test_private_projections_never_enter_public_sprite_mapper(tmp_path):
    ordinary=projection(tmp_path)
    with pytest.raises(PermissionError):
        select_character_parts(replace(ordinary,audience=AudienceScope.PRIVATE))
    with pytest.raises(ValueError):
        select_character_parts(ordinary,gaze="camera_face_tracking")


def test_unknown_hair_is_safe_fallback_and_never_pretends_new_art_exists(tmp_path):
    base=projection(tmp_path)
    changed=replace(
        base,appearance=replace(base.appearance,hairstyle="waist_length_ribbon_curls"),
    )
    result=select_character_parts(changed)
    assert result.as_dict()["hair_front"]=="long_layered"
    assert result.warnings



def test_independent_wink_changes_only_one_eye(tmp_path):
    p=projection(tmp_path)
    chosen=select_character_parts(p,expression="wink").as_dict()
    assert chosen["eye_left"]=="closed"
    assert chosen["eye_right"]=="open"
    assert chosen["brow_left"]=="neutral"
    assert chosen["brow_right"]=="neutral"
