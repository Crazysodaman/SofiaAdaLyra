"""Offline safety and accuracy tests for prompt editing."""
import copy
import json
from pathlib import Path

import pytest

from sofia.creative.comfyui_prompt_controller import WorkflowEditError, prepare, main


def workflow():
    return {
        "10": {"class_type": "CLIPTextEncode", "inputs": {"text": "original +", "clip": ["20", 1]}},
        "11": {"class_type": "CLIPTextEncode", "inputs": {"text": "original -", "clip": ["20", 1]}},
        "12": {"class_type": "KSampler", "inputs": {"seed": 21, "positive": ["57", 0], "negative": ["57", 1]}},
        "20": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "waiIllustriousSDXL_v170.safetensors"}},
        "24": {"class_type": "ImageScale", "inputs": {"upscale_method": "nearest-exact", "width": 1792, "height": 2688}},
        "57": {"class_type": "ControlNetApplyAdvanced", "inputs": {"strength": .85}},
    }


def test_only_requested_text_changes():
    original = workflow()
    pristine = copy.deepcopy(original)
    updated, changes = prepare(original, positive="new character details")
    assert updated["10"]["inputs"]["text"] == "new character details"
    assert updated["11"] == original["11"]
    assert updated["12"] == original["12"]
    assert updated["57"] == original["57"]
    assert original == pristine
    assert changes == {"positive": "10"}


def test_upscale_is_opt_in():
    original = workflow()
    updated, _ = prepare(original, negative="changed", fix_upscale=True)
    assert updated["24"]["inputs"]["upscale_method"] == "lanczos"
    assert original["24"]["inputs"]["upscale_method"] == "nearest-exact"


def test_reject_changed_nodes():
    original = workflow()
    original["10"]["class_type"] = "AnythingElse"
    with pytest.raises(WorkflowEditError):
        prepare(original, positive="test")


def test_refuse_original_overwrite(tmp_path):
    p = tmp_path / "source.json"
    p.write_text(json.dumps(workflow()))
    with pytest.raises(SystemExit):
        main(["--workflow", str(p), "--output", str(p), "--fix-upscale"])
    assert json.loads(p.read_text()) == workflow()


def test_cli_prepares_without_submitting(tmp_path, capsys):
    source, text, output = [tmp_path / name for name in ("source.json", "prompt.txt", "prepared.json")]
    source.write_text(json.dumps(workflow()))
    text.write_text("front-facing sofia")
    assert main(["--workflow", str(source), "--positive-file", str(text), "--output", str(output), "--fix-upscale"]) == 0
    data = json.loads(output.read_text())
    assert data["10"]["inputs"]["text"] == "front-facing sofia"
    assert data["12"]["inputs"]["seed"] == 21
    assert json.loads(capsys.readouterr().out)["submitted"] is False
