"""Owner-operated PUBLIC 2D scene editor and offline export CLI.

No model, camera, keyboard automation, private art, or change to sofia.db.
A saved public scene appears automatically in the existing desktop 2D canvas.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
import os

from .presentation import AppearanceState, AttireMode, AudienceScope, PresentationProjection
from .scene_compositor import (
    SceneSettings, _pil, compose_public_scene, export_scene_png, preset_path,
    import_public_background, load_scene_preset, load_public_background,
    save_scene_preset,
)
from .vtuber_asset_bundle import Avatar2DAssetError
from .wardrobe_catalog import build_starter_wardrobe
from sofia.config import production_state_path
from sofia.ui.avatar2d_installation import discover_public_avatar2d_root


def _available_public_catalog(state_path):
    # Built-in authoring metadata only. Never create or mutate the production DB.
    return build_starter_wardrobe(state_path=state_path)


def _public_projection(catalog, outfit_id: str):
    plan = next((p for p in catalog.presets
        if p.outfit_id == outfit_id and not p.private_only
        and catalog.wardrobe.selection(p.item_ids).covered_default), None)
    if plan is None:
        raise Avatar2DAssetError("unknown or non-public outfit")
    return PresentationProjection(
        audience=AudienceScope.PUBLIC,
        source_revision=1,
        attire=AttireMode.CLOTHED,
        outfit_id=plan.outfit_id,
        item_ids=plan.item_ids,
        appearance=AppearanceState(
            hairstyle="long layered", hair_color="deep crimson",
            tail_color="dark violet", eye_color="violet",
        ),
        private_fallback_used=False,
        reason="owner selected public scene editor view",
    )


def _import_local_background(public_root, image_path: Path):
    """Owner chooses a local still picture; store only an RGBA public derivative."""
    Image, _, ImageOps = _pil()
    if image_path.is_symlink() or not image_path.is_file():
        raise Avatar2DAssetError("background input must be a local regular file")
    if image_path.stat().st_size > 25 * 1024 * 1024:
        raise Avatar2DAssetError("background source too large")
    try:
        with Image.open(image_path) as raw:
            if raw.width * raw.height > 12_000_000:
                raise Avatar2DAssetError("background source exceeds pixel limit")
            image = ImageOps.exif_transpose(raw).convert("RGBA")
    except (OSError, ValueError) as exc:
        raise Avatar2DAssetError("invalid background image") from exc
    data = BytesIO()
    image.save(data, "PNG", optimize=True)
    encoded = data.getvalue()
    if len(encoded) > 16 * 1024 * 1024:
        raise Avatar2DAssetError("converted background exceeds public PNG size limit")
    name = "owner-" + sha256(encoded).hexdigest()[:20]
    try:
        digest = import_public_background(public_root, name, encoded)
    except FileExistsError:
        from hashlib import sha256 as hash_image
        digest = hash_image(encoded).hexdigest()
        load_public_background(public_root, name, digest)
    return name, digest


def _backgrounds(public_root):
    folder = public_root / "scenes" / "backgrounds"
    if not folder.is_dir() or folder.is_symlink():
        return {}
    result = {}
    for item in sorted(folder.iterdir()):
        if item.is_symlink() or not item.is_dir():
            continue
        try:
            manifest_path = item / "manifest.json"
            if manifest_path.is_symlink():
                continue
            metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
            digest = metadata["sha256"]
            load_public_background(public_root, item.name, digest)
            result[item.name] = digest
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


class PublicSceneEditor:
    """Small real Tk GUI with editable outfit, background and live preview."""
    def __init__(self, *, public_root: Path, catalog, outfit_id: str):
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        from PIL import ImageTk

        self.tk, self.ttk = tk, ttk
        self.filedialog, self.messagebox = filedialog, messagebox
        self.ImageTk = ImageTk
        self.root = tk.Tk()
        self.root.title("Sofía · Public 2D Scene Editor")
        self.root.geometry("900x745")
        self.public_root, self.catalog = public_root, catalog
        self.picture = None

        choices = tuple(p.outfit_id for p in catalog.presets if (
            not p.private_only and catalog.wardrobe.selection(p.item_ids).covered_default
        ))
        if outfit_id not in choices:
            raise Avatar2DAssetError("editor outfit not in public wardrobe")
        self.outfit = tk.StringVar(value=outfit_id)
        self.background = tk.StringVar()
        self.scale = tk.DoubleVar(value=.85)
        self.x = tk.DoubleVar(value=.5)
        self.y = tk.DoubleVar(value=1.0)
        self.blur = tk.DoubleVar(value=0)
        self.dim = tk.DoubleVar(value=0)
        self.shadow = tk.DoubleVar(value=.2)
        self.fit = tk.StringVar(value="cover")
        self.status = tk.StringVar(value="Select a background to begin")

        parent = ttk.Frame(self.root, padding=14)
        parent.pack(fill="both", expand=True)
        left = ttk.Frame(parent)
        left.pack(side="left", fill="y", padx=(0, 12))
        right = ttk.Frame(parent)
        right.pack(side="right", fill="both", expand=True)
        ttk.Label(left, text="Outfit (public only)").pack(anchor="w")
        box = ttk.Combobox(left, values=choices, state="readonly",
                            textvariable=self.outfit, width=31)
        box.pack(anchor="w", pady=(0, 10))
        box.bind("<<ComboboxSelected>>", lambda _e: self._outfit_changed())
        ttk.Label(left, text="Background").pack(anchor="w")
        self.bg_box = ttk.Combobox(left, values=(), state="readonly",
                                    textvariable=self.background, width=31)
        self.bg_box.pack(anchor="w")
        self.bg_box.bind("<<ComboboxSelected>>", lambda _e: self.preview())
        ttk.Button(left, text="Import PNG / JPG background…",
                   command=self._import).pack(fill="x", pady=(5, 12))
        for label, variable, minimum, maximum in (
            ("Character size", self.scale, .15, 2),
            ("Horizontal position", self.x, -.25, 1.25),
            ("Vertical position", self.y, 0, 1.5),
            ("Background blur", self.blur, 0, 16),
            ("Background dimming", self.dim, 0, .9),
            ("Character shadow", self.shadow, 0, 1),
        ):
            ttk.Label(left, text=label).pack(anchor="w")
            ttk.Scale(left, variable=variable, from_=minimum, to=maximum,
                      command=lambda _v: self.preview()).pack(fill="x", pady=(0, 7))
        ttk.Label(left, text="Background fit").pack(anchor="w")
        fitbox = ttk.Combobox(left, textvariable=self.fit, state="readonly",
                              values=("cover", "contain"), width=26)
        fitbox.pack(fill="x", pady=(0, 12))
        fitbox.bind("<<ComboboxSelected>>", lambda _e: self.preview())
        ttk.Button(left, text="Save outfit scene preset", command=self.save).pack(fill="x", pady=4)
        ttk.Button(left, text="Export scene PNG…", command=self.export).pack(fill="x", pady=4)
        ttk.Label(left, text="Public-only; no canonical wardrobe changes.",
                  wraplength=260).pack(anchor="w", pady=14)
        ttk.Label(right, text="Preview").pack(anchor="w")
        self.canvas = ttk.Label(right, anchor="center")
        self.canvas.pack(fill="both", expand=True)
        ttk.Label(right, textvariable=self.status, wraplength=445).pack(fill="x", pady=5)
        self._refresh_backgrounds()
        self._outfit_changed()

    def _refresh_backgrounds(self):
        self.available_backgrounds = _backgrounds(self.public_root)
        self.bg_box.configure(values=tuple(self.available_backgrounds))
        if self.background.get() not in self.available_backgrounds:
            self.background.set(next(iter(self.available_backgrounds), ""))

    def _outfit_changed(self):
        projection = _public_projection(self.catalog, self.outfit.get())
        try:
            saved = load_scene_preset(
                self.public_root, projection, catalog=self.catalog
            )
        except (Avatar2DAssetError, ValueError) as exc:
            self.status.set("Saved scene is invalid: " + str(exc))
            return
        if saved is not None:
            self.background.set(saved.background_id)
            for name in ("scale", "x", "y", "blur", "dim", "shadow"):
                getattr(self, name).set(getattr(saved, name))
            self.fit.set(saved.background_fit)
        self.preview()

    def scene(self):
        name = self.background.get()
        if name not in self.available_backgrounds:
            raise Avatar2DAssetError("choose or import a public background first")
        projection = _public_projection(self.catalog, self.outfit.get())
        scene = SceneSettings(
            outfit_id=projection.outfit_id, item_ids=projection.item_ids,
            background_id=name, background_sha256=self.available_backgrounds[name],
            scale=round(self.scale.get(), 4), x=round(self.x.get(), 4),
            y=round(self.y.get(), 4), blur=round(self.blur.get(), 3),
            dim=round(self.dim.get(), 3), shadow=round(self.shadow.get(), 3),
            background_fit=self.fit.get(),
        )
        return projection, scene

    def preview(self):
        try:
            projection, scene = self.scene()
            composed, source = compose_public_scene(
                self.public_root, projection, catalog=self.catalog, scene=scene,
            )
            composed.thumbnail((390, 600))
            self.picture = self.ImageTk.PhotoImage(composed)
            self.canvas.configure(image=self.picture)
            self.status.set("Preview: " + projection.outfit_id + " · " + source)
        except Exception as exc:
            self.status.set(type(exc).__name__ + ": " + str(exc))

    def _import(self):
        filename = self.filedialog.askopenfilename(
            parent=self.root, title="Import public background",
            filetypes=(("Image files", "*.png *.jpg *.jpeg"),),
        )
        if not filename:
            return
        try:
            name, _ = _import_local_background(self.public_root, Path(filename))
            self._refresh_backgrounds()
            self.background.set(name)
            self.preview()
        except Exception as exc:
            self.messagebox.showerror("Background not imported", str(exc), parent=self.root)

    def save(self):
        try:
            projection, scene = self.scene()
            # No write unless a real verified art source is compositable.
            compose_public_scene(self.public_root, projection, catalog=self.catalog, scene=scene)
            path = self.public_root / "scenes" / "presets" / (scene.outfit_id + ".json")
            if path.exists() and not self.messagebox.askyesno(
                "Replace preset?", "Replace the public scene preset for " + scene.outfit_id + "?",
                parent=self.root,
            ):
                return
            save_scene_preset(self.public_root, scene, catalog=self.catalog,
                              replace_existing=path.exists())
            self.status.set("Saved " + str(path) + ". Reopen Sofía to see this scene.")
        except Exception as exc:
            self.messagebox.showerror("Cannot save scene", str(exc), parent=self.root)

    def export(self):
        try:
            projection, scene = self.scene()
            target = self.filedialog.asksaveasfilename(
                parent=self.root, defaultextension=".png",
                filetypes=(("PNG", "*.png"),),
            )
            if not target:
                return
            dest = Path(target)
            if dest.exists() and not self.messagebox.askyesno(
                "Replace exported scene?", "Replace " + dest.name + "?",
                parent=self.root,
            ):
                return
            export_scene_png(self.public_root, projection, catalog=self.catalog,
                             scene=scene, destination=dest, replace_existing=dest.exists())
            self.status.set("Exported " + str(dest))
        except Exception as exc:
            self.messagebox.showerror("Cannot export scene", str(exc), parent=self.root)

    def run(self):
        self.root.mainloop()


def main(argv=None):
    p = argparse.ArgumentParser(description="Edit/export Sofía PUBLIC 2D scenes")
    p.add_argument("--root", type=Path, help="existing public 2D asset root")
    p.add_argument("--outfit", help="explicit approved public outfit ID")
    p.add_argument("--state-path", type=Path, help="canonical database path (read-only)")
    p.add_argument("--import-background", type=Path, help="owner-selected PNG/JPG to import")
    p.add_argument("--export", type=Path, help="render selected scene to PNG without opening UI")
    p.add_argument("--save", action="store_true", help="save a default scene for chosen background")
    p.add_argument("--replace", action="store_true", help="permit replacing existing scene/output")
    args = p.parse_args(argv)
    from .vtuber_public_diagnose import _public_snapshot
    root = args.root or discover_public_avatar2d_root(
        os.environ.get("SOFIA_AVATAR2D_PUBLIC_ROOT"),
        local_app_data=os.environ.get("LOCALAPPDATA"),
    )
    if root is None or not root.is_dir():
        p.error("public avatar pack missing; run vtuber_public_setup first")
    state = args.state_path or production_state_path()
    catalog = _available_public_catalog(state)
    snapshot, _ = _public_snapshot(state)
    outfit_id = args.outfit or ((snapshot or {}).get("outfit_id")) or "day.default"
    projection = _public_projection(catalog, outfit_id)
    if args.import_background:
        name, digest = _import_local_background(root, args.import_background)
        print("Imported public background:", name)
    else:
        backgrounds = _backgrounds(root)
        name = next(iter(backgrounds), None)
        digest = backgrounds.get(name) if name else None
    if args.save:
        if not name:
            p.error("no public background; use --import-background first")
        preset = SceneSettings(
            outfit_id=projection.outfit_id, item_ids=projection.item_ids,
            background_id=name, background_sha256=digest,
        )
        save_scene_preset(root, preset, catalog=catalog, replace_existing=args.replace)
        print("Saved public scene:", preset_path(root, outfit_id))
    if args.export:
        preset = load_scene_preset(root, projection, catalog=catalog)
        if preset is None:
            p.error("no saved public scene for selected outfit")
        export_scene_png(root, projection, catalog=catalog, scene=preset,
                         destination=args.export, replace_existing=args.replace)
        print("Exported scene:", args.export)
    elif not args.save and not args.import_background:
        PublicSceneEditor(public_root=root, catalog=catalog, outfit_id=outfit_id).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
