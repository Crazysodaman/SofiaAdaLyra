"""Static/offline checks only; Blender is NOT installed in this test environment."""
from pathlib import Path
import ast

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "avatar" / "blender_blockout.py"


def test_blender_script_parses_without_blender_dependency():
    ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_script_does_not_delete_the_scene_or_run_external_commands():
    text = SOURCE.read_text(encoding="utf-8")
    assert "bpy.ops.object.delete" not in text
    assert "bpy.ops.wm.read_factory_settings" not in text
    assert "subprocess" not in text
    assert "bpy.ops.wm.save_as_mainfile" in text


def test_slot_anchors_and_dressed_blockout_named():
    text = SOURCE.read_text(encoding="utf-8")
    for name in ("left_forearm", "right_forearm", "torso", "pelvis", "ears", "tail", "GARMENT_oversized_tee", "GARMENT_sweatpants", "GARMENT_leather_gauntlet"):
        assert name in text or (name in ("left_forearm", "right_forearm") and "side + \"_forearm\"" in text)
    assert 'parent["public_display_authorized"] = False' in text
