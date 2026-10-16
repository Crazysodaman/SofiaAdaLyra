"""Optional real layered PNG avatar frontend for the existing Tk workbench.

This first backend is PUBLIC ONLY. Its input is a trusted, already-public
PresentationProjection plus the canonical wardrobe. No protected artwork is
opened and no new appearance authority or event route is introduced.

Fallback to TkAvatarRenderer remains available when the local sprite pack is
absent, unsuitable or not yet painted. All image data is loaded and decoded
only in the GUI thread. The configured art path is explicit and never scanned
beyond the exact current outfit ID.
"""
from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sofia.avatar.presentation import AttireMode, AudienceScope, PresentationProjection
from sofia.avatar.vtuber_asset_bundle import (
    Avatar2DArtSelection, Avatar2DAssetError, _read_bundle,
)
from sofia.avatar.vtuber_layer_stack import assemble_avatar2d_layers
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_matrix import build_wardrobe_matrix
from sofia.ui.avatar_renderer import AvatarRenderRequest, TkAvatarRenderer


class TkLayered2DRenderer:
    """Render real verified PNG sprites on Tk with honest fallback receipts."""

    backend_name = "tk-layered2d-public-or-symbolic-fallback-v1"

    def __init__(
        self,
        *,
        root,
        canvas,
        public_root: Path,
        state_path: Path | None = None,
        fallback: TkAvatarRenderer | None = None,
    ) -> None:
        if not isinstance(public_root, Path) or not str(public_root).strip():
            raise TypeError("explicit public sprite path required")
        self.root = root
        self.canvas = canvas
        self.public_root = public_root
        self.fallback = fallback or TkAvatarRenderer(root=root,canvas=canvas)
        # This reads existing reviewed items but doesn't mutate the canonical DB.
        self.catalog = build_starter_wardrobe(state_path=state_path)
        self._active_decision: str | None = None
        self._pending_after: object | None = None
        self._images: list = []
        self._last_revision: int | None = None
        self._last_digest: str | None = None

    @staticmethod
    def _verified_public(projection: PresentationProjection) -> bool:
        return (
            isinstance(projection, PresentationProjection)
            and projection.audience is AudienceScope.PUBLIC
            and projection.attire is AttireMode.CLOTHED
            and projection.outfit_id is not None
        )

    def _paint(self, projection: PresentationProjection, *, shift: int = 0) -> int:
        """Decode and draw the actual selected public artwork layers.

        Return the count that the Tk canvas accepted. Never fabricate a
        drawable image from wardrobe metadata or a model-generated filename.
        """
        if not self._verified_public(projection):
            raise Avatar2DAssetError("public-only layered renderer")
        if not projection.outfit_id or "/" in projection.outfit_id or "\\" in projection.outfit_id:
            raise Avatar2DAssetError("invalid public outfit ID")
        directory = self.public_root / "outfits" / projection.outfit_id
        art = _read_bundle(
            directory,
            audience=AudienceScope.PUBLIC,
            attire=AttireMode.CLOTHED,
            outfit_id=projection.outfit_id,
        )
        try:
            selection = Avatar2DArtSelection(
                "public", projection, art, "verified current public wardrobe",
            )
            matrix = build_wardrobe_matrix(self.catalog, projection.item_ids)
            plan = assemble_avatar2d_layers(selection, matrix=matrix)
            from tkinter import PhotoImage

            images = []
            for sprite in plan.draw_layers:
                source = art.images[sprite.sprite_id]
                # Tk 8.6+ PNG decoding accepts base64 data; shrink the 320x400
                # full-canvas layers equally to fit the existing 300px viewport.
                image = PhotoImage(
                    data=b64encode(source).decode("ascii"), format="png",
                ).subsample(2,2)
                images.append(image)
            # Prepare all images before deleting an already displayed frame.
            self.canvas.delete("avatar")
            self.canvas.delete("avatar2d")
            xpos = max(85, self.canvas.winfo_width()//2)
            ypos = 22 + shift
            for image in images:
                self.canvas.create_image(
                    xpos,ypos,anchor="n",image=image,tags="avatar2d",
                )
            self._images = images
            self._last_revision = plan.presentation_revision
            self._last_digest = plan.bundle_digest
            return len(images)
        finally:
            art.close()

    def _fallback_render(self, request: AvatarRenderRequest, completed) -> None:
        self.canvas.delete("avatar2d")
        self._images.clear()
        self._last_revision = None
        self._last_digest = None
        self.fallback.render(request,completed=completed)

    def render(self, request: AvatarRenderRequest, *, completed) -> None:
        if not isinstance(request, AvatarRenderRequest):
            raise TypeError("avatar renderer requires AvatarRenderRequest")
        if not callable(completed):
            raise TypeError("completion callback required")
        # Stop can cancel the prior frame before completion, never report the
        # old frame as if it actually finished.
        self.stop()
        if not self._verified_public(request.presentation):
            # A public-only renderer must never hand a private/nude request to
            # its symbolic fallback, which has no private-art grant context.
            self.canvas.delete("avatar")
            self.canvas.delete("avatar2d")
            self._images.clear()
            completed(
                request.decision.decision_id, False,
                "no audience-safe covered public projection available",
            )
            return
        try:
            count = self._paint(request.presentation)
        except Exception:
            # Missing/invalid art and GUI decoder errors never crash chat.
            self._fallback_render(request, completed)
            return
        self._active_decision = request.decision.decision_id

        def finish():
            self._pending_after = None
            expected = self._active_decision
            self._active_decision = None
            if expected != request.decision.decision_id:
                return
            visible = True
            if hasattr(self.canvas,"winfo_viewable"):
                visible = bool(self.canvas.winfo_viewable())
            completed(
                request.decision.decision_id, visible,
                (
                    f"painted {count} verified public PNG sprite layer(s), "
                    f"presentation revision {request.presentation.source_revision}"
                    if visible else "avatar window not visible; no frame receipt"
                ),
            )
        self._pending_after = self.root.after(45,finish)

    def render_idle(self, presentation: PresentationProjection) -> None:
        self.stop()
        if not self._verified_public(presentation):
            self.canvas.delete("avatar")
            self.canvas.delete("avatar2d")
            self._images.clear()
            return
        try:
            self._paint(presentation)
        except Exception:
            self.canvas.delete("avatar2d")
            self._images.clear()
            self.fallback.render_idle(presentation)

    def stop(self) -> str | None:
        decision = self._active_decision
        self._active_decision = None
        if self._pending_after is not None:
            try:
                self.root.after_cancel(self._pending_after)
            except (AttributeError, ValueError):
                pass
            self._pending_after = None
        old = self.fallback.stop()
        return decision or old
