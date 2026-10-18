"""Edit only the reviewed prompt slots in a ComfyUI API workflow."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

class WorkflowEditError(ValueError):
    pass

# Sofía's reviewed Main 2d image.json API graph.
PROMPT_NODES = {"positive": "10", "negative": "11"}
SAMPLER_NODE = "12"
UPSCALE_NODE = "24"


def _load(path: Path) -> dict:
    if path.stat().st_size > 2_000_000:
        raise WorkflowEditError("workflow exceeds size limit")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise WorkflowEditError("cannot read API-format workflow") from exc
    if not isinstance(data, dict) or not data:
        raise WorkflowEditError("expected ComfyUI API-format mapping")
    return data


def prepare(workflow: dict, *, positive: str | None = None, negative: str | None = None,
            fix_upscale: bool = False) -> tuple[dict, dict]:
    if positive is None and negative is None and not fix_upscale:
        raise WorkflowEditError("no changes requested")
    edited = copy.deepcopy(workflow)
    changed = {}
    for label, text in (("positive", positive), ("negative", negative)):
        if text is None:
            continue
        if not isinstance(text, str) or not text.strip() or len(text) > 12_000:
            raise WorkflowEditError(f"invalid {label} prompt")
        node_id = PROMPT_NODES[label]
        node = edited.get(node_id)
        if not isinstance(node, dict) or node.get("class_type") != "CLIPTextEncode" or not isinstance(node.get("inputs"), dict) or not isinstance(node["inputs"].get("text"), str):
            raise WorkflowEditError(f"unexpected {label} prompt node; graph may have changed")
        node["inputs"]["text"] = text
        changed[label] = node_id
    if fix_upscale:
        node = edited.get(UPSCALE_NODE)
        if not isinstance(node, dict) or node.get("class_type") != "ImageScale" or not isinstance(node.get("inputs"), dict) or node["inputs"].get("upscale_method") not in {"nearest-exact", "lanczos"}:
            raise WorkflowEditError("upscale node differs from reviewed graph")
        node["inputs"]["upscale_method"] = "lanczos"
        changed["upscale"] = UPSCALE_NODE
    node = edited.get(SAMPLER_NODE)
    if not isinstance(node, dict) or node.get("class_type") != "KSampler":
        raise WorkflowEditError("unexpected KSampler node")
    # Do not adjust checkpoints, pose conditioning, sampler, seed or dimensions.
    return edited, changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create a reviewable ComfyUI workflow; never submits jobs")
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--positive-file", type=Path)
    parser.add_argument("--negative-file", type=Path)
    parser.add_argument("--fix-upscale", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.workflow.resolve() == args.output.resolve():
            raise WorkflowEditError("refusing to overwrite the original workflow")
        pos = args.positive_file.read_text(encoding="utf-8") if args.positive_file else None
        neg = args.negative_file.read_text(encoding="utf-8") if args.negative_file else None
        original = _load(args.workflow)
        updated, changes = prepare(original, positive=pos, negative=neg, fix_upscale=args.fix_upscale)
        payload = json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        print(json.dumps({"output": str(args.output), "modified_nodes": changes, "sha256": hashlib.sha256(payload.encode()).hexdigest(), "submitted": False}, indent=2))
        return 0
    except (WorkflowEditError, OSError, UnicodeError) as exc:
        parser.exit(2, f"workflow preparation: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
