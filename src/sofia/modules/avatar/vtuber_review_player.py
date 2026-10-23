"""Owner-only local 2D sprite animation reviewer, not the live avatar renderer.

Allows Venus to VISUALLY inspect real independent eye, brow and mouth swaps
against staged Batch09/10/11/12/13 art. It never writes Sofia state, grants,
Public-V2, canonical assets or wardrobe. No simulated lip-sync is ever
reported as a voice receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import argparse
import json
from pathlib import Path

from .vtuber_mouth_viseme_review import (
    compose_review_frame, verify_review_mouths,
)
from .vtuber_independent_features import verify_independent_features


@dataclass(frozen=True, slots=True)
class PreviewStep:
    name: str
    expression: str
    duration_ms: int


_STEPS = (
    PreviewStep("Neutral", "neutral", 650),
    PreviewStep("Blink", "blink", 130),
    PreviewStep("Open", "neutral", 520),
    PreviewStep("Left wink", "left_wink", 430),
    PreviewStep("Right wink", "right_wink", 430),
    PreviewStep("Smile", "smile", 670),
    PreviewStep("Open speech (A)", "A", 340),
    PreviewStep("Wide speech (E)", "E", 340),
    PreviewStep("Rounded speech (O)", "O", 340),
    PreviewStep("Closed speech (M)", "M", 410),
    PreviewStep("Neutral", "neutral", 650),
)
assert all(100 <= step.duration_ms <= 1000 for step in _STEPS)


def preview_steps() -> tuple[PreviewStep, ...]:
    return _STEPS


def review_directory_status(*, foundation: Path, features: Path, mouths: Path) -> tuple[dict, ...]:
    """Report exactly which staged package path is missing or invalid.

    Inspection is read-only; merely checking directory existence never
    activates the avatar, reads protected artwork or writes user state.
    """
    folders = (
        ("Batch 09 head foundation", foundation),
        ("Batch 10/11 eyes and brows", features),
        ("Batch 12/13 mouths and visemes", mouths),
    )
    result = []
    for label, folder in folders:
        if not isinstance(folder, Path) or not folder.is_absolute():
            reason = "not an absolute path (PowerShell variable may be empty)"
        elif not folder.is_dir():
            reason = "directory does not exist (package not staged or wrong path)"
        elif any(part.is_symlink() for part in (folder, *folder.parents)):
            reason = "symlinked directory is not allowed"
        elif not (folder / "manifest.json").is_file():
            reason = "manifest.json missing (wrong folder or incomplete staging)"
        else:
            reason = "ok"
        result.append({"batch": label, "path": str(folder), "status": reason})
    return tuple(result)


def run_local_preview(
    *, foundation: Path, features: Path, mouths: Path,
    source_root: Path | None = None, canonical_body: Path | None = None,
) -> None:
    if (source_root is None) != (canonical_body is None):
        raise ValueError(
            "For a complete character preview, supply BOTH "
            "--source-root and --canonical-body"
        )
    for item in review_directory_status(
        foundation=foundation, features=features, mouths=mouths,
    ):
        if item["status"] != "ok":
            raise ValueError(
                f"{item['batch']}: {item['status']}. Path: {item['path']}. "
                "Stage/verify that batch, or redefine your PowerShell path variables."
            )
    verify_review_mouths(
        mouths, foundation_root=foundation, features_root=features,
    )
    verify_independent_features(features, foundation_root=foundation)
    try:
        import tkinter as tk
        from PIL import Image, ImageTk, ImageOps
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError("Tkinter and Pillow ImageTk required for local sprite review") from exc

    # Prepared once, not per animation frame. In review mode, body and
    # hairstyles are separate, inspected source art. The approved source
    # digests are pinned by the existing hair/ear registration module.
    frame_back = frame_front = None
    if source_root is not None:
        from .vtuber_batch09_foundation import verify_head_foundation
        from .vtuber_hair_ear_review import (
            _private_path, _load, _registered, _CANDIDATE_BOXES,
        )
        for path in (source_root, canonical_body):
            _private_path(path)
        verify_head_foundation(foundation, canonical_body=canonical_body)
        if not source_root.is_dir():
            raise ValueError(f"approved hair/ear source missing: {source_root}")
        artwork = {
            "hair_back_main.png": source_root / "layers/hair/hair_back_main.png",
            "hair_front_bangs.png": source_root / "layers/hair/hair_front_bangs.png",
            "ear_pose_01.png": source_root / "layers/ears/ear_pose_01.png",
            "ear_pose_06.png": source_root / "layers/ears/ear_pose_06.png",
        }
        fitted = {
            name: _registered(_load(path, name=name), _CANDIDATE_BOXES[name])
            for name, path in artwork.items()
        }
        with Image.open(canonical_body) as source:
            if source.format != "PNG" or source.mode != "RGBA" or source.size != (2048, 2560):
                raise ValueError("canonical body must be 2048x2560 RGBA PNG")
            body = source.copy()
        frame_back = Image.new("RGBA", (2048, 2560))
        frame_back.alpha_composite(fitted["hair_back_main.png"])
        frame_back.alpha_composite(body)
        frame_back.alpha_composite(fitted["ear_pose_01.png"])
        frame_back.alpha_composite(fitted["ear_pose_06.png"])
        frame_front = fitted["hair_front_bangs.png"]

    window = tk.Tk()
    window.title("Sofía | PRIVATE ART REVIEW ONLY (not live renderer)")
    window.geometry("720x790" if frame_back is not None else "560x610")
    window.configure(bg="#231e30")
    panel = tk.Label(window, bg="#231e30")
    panel.pack(pady=8)
    status = tk.StringVar(value="Staged artwork review. No production activation.")
    label = tk.Label(window, textvariable=status, bg="#231e30", fg="#e9dced",
                     font=("Segoe UI", 11), wraplength=500)
    label.pack(pady=8)
    frame_index = 0
    running = True
    pending = None
    photo = None
    closed = False

    @lru_cache(maxsize=12)
    def scaled_frame(expression: str):
        # Decode/resize each distinct source frame just once per preview
        # session; do not reprocess full 2048x2560 layers every 130 ms.
        image = compose_review_frame(
            foundation_root=foundation, features_root=features,
            mouths_root=mouths, expression=expression,
        )
        if frame_back is not None:
            assembled = frame_back.copy()
            assembled.alpha_composite(image)
            assembled.alpha_composite(frame_front)
            return ImageOps.contain(
                assembled.crop((710, 0, 1334, 620)), (660, 630),
                Image.Resampling.LANCZOS,
            )
        return ImageOps.contain(
            image.crop((830, 54, 1186, 458)), (486, 492),
            Image.Resampling.LANCZOS,
        )

    def draw(index: int) -> None:
        nonlocal photo, frame_index
        frame_index = index % len(_STEPS)
        step = _STEPS[frame_index]
        photo = ImageTk.PhotoImage(scaled_frame(step.expression))
        panel.configure(image=photo)
        panel.image = photo
        status.set(
            f"Frame {frame_index+1}/{len(_STEPS)}: {step.name}  "
            "| ARTWORK DEMO, NOT AUDIO-DRIVEN"
        )

    def cancel() -> None:
        nonlocal pending
        if pending is not None:
            window.after_cancel(pending)
            pending = None

    def schedule() -> None:
        nonlocal pending
        cancel()
        if running and not closed:
            pending = window.after(_STEPS[frame_index].duration_ms, next_frame)

    def next_frame() -> None:
        nonlocal pending
        pending = None
        if closed:
            return
        draw(frame_index + 1)
        schedule()

    def manual(delta: int) -> None:
        nonlocal running
        running = False
        cancel()
        draw(frame_index + delta)

    def toggle() -> None:
        nonlocal running
        running = not running
        play_btn.configure(text="Pause" if running else "Play")
        if running:
            schedule()
        else:
            cancel()

    def close() -> None:
        nonlocal closed
        closed = True
        cancel()
        window.destroy()

    controls = tk.Frame(window, bg="#231e30")
    controls.pack(pady=10)
    tk.Button(controls, text="Previous", command=lambda: manual(-1)).pack(
        side="left", padx=5,
    )
    play_btn = tk.Button(controls, text="Pause", command=toggle)
    play_btn.pack(side="left", padx=5)
    tk.Button(controls, text="Next", command=lambda: manual(1)).pack(
        side="left", padx=5,
    )
    tk.Button(controls, text="Close", command=close).pack(
        side="left", padx=5,
    )
    window.protocol("WM_DELETE_WINDOW", close)
    draw(0)
    schedule()
    window.mainloop()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Locally preview validated but NOT production-activated source sprite swaps"
    )
    parser.add_argument("--foundation-root", type=Path, required=True)
    parser.add_argument("--features-root", type=Path, required=True)
    parser.add_argument("--mouths-root", type=Path, required=True)
    parser.add_argument(
        "--source-root", type=Path,
        help="Optional PRIVATE approved CoreLayers/v1 source for full character review",
    )
    parser.add_argument(
        "--canonical-body", type=Path,
        help="Required with --source-root: canonical body PNG",
    )
    parser.add_argument(
        "--check-paths", action="store_true",
        help="Show exact staged-directory problems without opening the Tk window",
    )
    args = parser.parse_args(argv)
    if args.check_paths:
        statuses = review_directory_status(
            foundation=args.foundation_root,
            features=args.features_root,
            mouths=args.mouths_root,
        )
        print(json.dumps(statuses, indent=2))
        return 0 if all(item["status"] == "ok" for item in statuses) else 2
    run_local_preview(
        foundation=args.foundation_root,
        features=args.features_root,
        mouths=args.mouths_root,
        source_root=args.source_root,
        canonical_body=args.canonical_body,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
