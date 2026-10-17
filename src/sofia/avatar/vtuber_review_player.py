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


def run_local_preview(*, foundation: Path, features: Path, mouths: Path) -> None:
    verify_review_mouths(
        mouths, foundation_root=foundation, features_root=features,
    )
    verify_independent_features(features, foundation_root=foundation)
    try:
        import tkinter as tk
        from PIL import ImageTk, ImageOps
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError("Tkinter and Pillow ImageTk required for local sprite review") from exc

    window = tk.Tk()
    window.title("Sofía | PRIVATE ART REVIEW ONLY (not live renderer)")
    window.geometry("560x610")
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
        return ImageOps.contain(image.crop((830, 54, 1186, 458)), (486, 492))

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
    args = parser.parse_args(argv)
    run_local_preview(
        foundation=args.foundation_root,
        features=args.features_root,
        mouths=args.mouths_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
