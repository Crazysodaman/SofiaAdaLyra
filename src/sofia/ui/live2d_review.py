"""Owner-operated Live2D preparation review window for Sofía Desktop.

This is a real, local artwork intake/review surface, not an automatic segmenter.
No model execution, GPU requests, hidden-art reconstruction or PSD claim.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
from uuid import uuid4

FACE_PARTS = (
    "Face_Base", "Hair_Back", "Hair_Front_Center", "Hair_Front_Left",
    "Hair_Front_Right", "Brow_L", "Brow_R", "Eye_L", "Eye_R",
    "Mouth_Neutral",
)

def create_review_job(source: Path, folder: Path, *, name: str = "Sofia_Face") -> Path:
    """Make a non-destructive, explicitly unapproved face-layer review job."""
    from PIL import Image
    if not source.is_file() or source.suffix.lower() != ".png":
        raise ValueError("select an existing PNG source image")
    if source.stat().st_size > 40_000_000:
        raise ValueError("source PNG exceeds the 40MB intake limit")
    with Image.open(source) as image:
        image.verify()
    with Image.open(source) as image:
        width, height = image.size
    if width < 256 or height < 256 or width * height > 35_000_000:
        raise ValueError("source dimensions unsupported")
    if folder.exists():
        raise FileExistsError("review job directory already exists; no overwrite")
    folder.mkdir(parents=True)
    try:
        shutil.copyfile(source, folder / "source.png")
        data = {
            "schema_version": 1, "job_id": uuid4().hex, "name": name,
            "mode": "face", "status": "awaiting_masks",
            "canvas": {"width": width, "height": height},
            "source": "source.png",
            "parts": [{"name": p, "status": "not_extracted", "approved": False}
                      for p in FACE_PARTS],
            "auto_extraction_performed": False, "psd_exported": False,
        }
        (folder / "manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return folder
    except Exception:
        shutil.rmtree(folder)
        raise

def open_review_window(parent, *, tk=None):
    """Present an actual image picker and persistent draft manifest inside Desktop."""
    if tk is None:
        import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Toplevel(parent)
    root.title("Sofía | Live2D Asset Prep")
    root.geometry("590x520")
    root.transient(parent)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Live2D Face Preparation", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Select an approved PNG. This first pass creates a review job, not fake layers.",
              wraplength=525).pack(anchor="w", pady=(8, 12))
    selected = tk.StringVar(master=root, value="No image selected")
    ttk.Label(frame, textvariable=selected, wraplength=525).pack(anchor="w")
    preview = ttk.Label(frame, text="Preview", anchor="center")
    preview.pack(fill="both", expand=True, pady=10)
    state = {"source": None, "preview": None}

    def choose():
        path = filedialog.askopenfilename(parent=root, title="Choose Sofía face PNG",
                                          filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                image = im.convert("RGBA")
                image.thumbnail((350, 280))
                photo = ImageTk.PhotoImage(image, master=root)
            state.update(source=Path(path), preview=photo)
            selected.set(path)
            preview.configure(image=photo, text="")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Cannot load image", str(exc), parent=root)

    def prepare():
        source = state["source"]
        if source is None:
            messagebox.showinfo("Image required", "Choose a PNG first.", parent=root)
            return
        destination = filedialog.askdirectory(parent=root, title="Choose parent folder for review job")
        if not destination:
            return
        folder = Path(destination) / ("Sofia_Face_" + uuid4().hex[:8])
        try:
            create_review_job(source, folder)
        except (OSError, ValueError, ImportError) as exc:
            messagebox.showerror("Preparation failed", str(exc), parent=root)
            return
        messagebox.showinfo("Review job created",
                            f"Saved image and parts checklist to:\n{folder}\n\n"
                            "Masks and artwork layers are NOT generated yet.", parent=root)

    def check_recovery():
        folder = filedialog.askdirectory(parent=root, title="Choose existing Live2D job folder")
        if not folder:
            return
        job = Path(folder)
        if not (job / "manifest.json").is_file():
            messagebox.showerror("Not a Live2D job", "This folder has no manifest.json", parent=root)
            return
        if not (job / "comfyui_job.json").is_file():
            messagebox.showinfo("No generation pending", "This review job has no saved ComfyUI submission. Your source and checklist remain available.", parent=root)
            return
        try:
            from sofia.creative.comfyui_bridge import ComfyUIBridge
            from sofia.creative.live2d_recovery import reconcile
            recovered = reconcile(job, ComfyUIBridge())
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("Cannot inspect job", str(exc), parent=root)
            return
        messagebox.showinfo("ComfyUI recovery", f"State: {recovered['status']}\\n\\n{recovered['last_check']}\\n\\nNo job was resubmitted.", parent=root)

    controls = ttk.Frame(frame)
    controls.pack(fill="x")
    ttk.Button(controls, text="Choose image…", command=choose).pack(side="left", padx=(0, 8))
    ttk.Button(controls, text="Create review job…", command=prepare).pack(side="left")
    ttk.Button(controls, text="Recover job…", command=check_recovery).pack(side="left", padx=(8, 0))\n    ttk.Button(controls, text="Close", command=root.destroy).pack(side="right")
    return root
