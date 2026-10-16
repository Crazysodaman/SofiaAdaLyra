"""Actual public layered 2D avatar rendering with independent character sprites.

Existing canonical wardrobe IDs supply clothing; modular face, eyes, mouth,
ears and tail sprites replace the old baked-in head/tail when an approved
character pack exists under PUBLIC_ROOT/character/.

All PNGs are checked before Tk decoding. A missing modular pack uses existing
fully verified legacy public outfit art. An invalid present pack falls back to
the separate symbolic renderer, never an unverified mixture of sprites.

No private assets, autonomous input events, inferred speech, or fabricated
gesture frames are introduced by this module.
"""
from __future__ import annotations

from base64 import b64encode
from hashlib import sha256
from pathlib import Path
from typing import Callable

from sofia.avatar.presentation import AttireMode, AudienceScope, PresentationProjection
from sofia.avatar.vtuber_asset_bundle import (
    Avatar2DArtSelection, Avatar2DAssetError, _read_bundle,
)
from sofia.avatar.vtuber_layer_stack import assemble_avatar2d_layers
from sofia.avatar.vtuber_character_bundle import load_selected_character_sprites
from sofia.avatar.vtuber_character_selection import select_character_parts
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.avatar.wardrobe_matrix import build_wardrobe_matrix
from sofia.ui.avatar_renderer import AvatarRenderRequest, TkAvatarRenderer


_CHARACTER_STACK_ORDER = {
    "tail": 50,
    "hair_back": 80,
    "ear_left": 100,
    "ear_right": 100,
    "face": 8000,
    "eye_left": 8100,
    "eye_right": 8100,
    "brow_left": 8200,
    "brow_right": 8200,
    "mouth": 8300,
    "freckles": 8400,
    "hair_front": 9000,
}


def _character_expression(decision) -> str:
    """Conservatively use expression intent already established by cognition."""
    labels = set(getattr(decision, "emotion_labels", ()) or ())
    if "skeptical" in labels or "focused" in labels:
        return "skeptical"
    if labels & {"happy", "joyful", "playful", "affectionate"}:
        return "smile"
    return "neutral"


def _gesture_frames(gesture: str | None) -> int:
    return 3 if gesture in (
        "tail-flick", "tail-swish", "slow-tail-sway",
        "ear-flick", "ear-perk", "blink", "wink", "tail-wag",
    ) else 1


def _frame_character_state(
    *,
    expression: str,
    gesture: str | None,
    index: int,
    frames: int,
) -> tuple[str, str | None]:
    if frames == 1:
        return expression, gesture
    if gesture in ("tail-flick", "tail-swish", "slow-tail-sway", "tail-wag"):
        return expression, gesture if index == 1 else None
    if gesture == "ear-flick":
        return expression, "ear-flatten" if index == 1 else "ear-perk"
    if gesture == "ear-perk":
        return expression, "ear-flatten" if index == 0 else "ear-perk"
    if gesture in ("blink", "wink"):
        return (gesture if index == 1 else expression), None
    return expression, gesture


class TkLayered2DRenderer:
    """Render checked PNG layers and acknowledge only displayed frames."""

    backend_name = "tk-layered2d-public-modular-or-symbolic-fallback-v2"

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
        self.catalog = build_starter_wardrobe(state_path=state_path)
        self._active_decision: str | None = None
        self._pending_after: object | None = None
        self._generation = 0
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

    def _paint(
        self,
        projection: PresentationProjection,
        *,
        expression: str = "neutral",
        gesture: str | None = None,
        shift: int = 0,
    ) -> tuple[int, bool]:
        """Paint the current checked outfit and optional modular face/fox parts.

        Return (number of real drawn PNG layers, character_pack_loaded).
        Every image is prepared before old canvas pixels are cleared.
        """
        if not self._verified_public(projection):
            raise Avatar2DAssetError("public-only layered renderer")
        if (
            not projection.outfit_id or "/" in projection.outfit_id
            or "\\" in projection.outfit_id
        ):
            raise Avatar2DAssetError("invalid public outfit ID")
        directory = self.public_root / "outfits" / projection.outfit_id
        art = _read_bundle(
            directory, audience=AudienceScope.PUBLIC,
            attire=AttireMode.CLOTHED, outfit_id=projection.outfit_id,
        )
        try:
            matrix = build_wardrobe_matrix(self.catalog, projection.item_ids)
            plan = assemble_avatar2d_layers(
                Avatar2DArtSelection(
                    "public", projection, art, "checked public wardrobe",
                ),
                matrix=matrix,
            )
            character_root = self.public_root / "character"
            modular = (character_root / "manifest.json").is_file()
            layers = []
            if modular:
                # Wardrobe base_body remains exactly once. Replace the older
                # baked-in back/face/front with independently animatable art.
                for sprite in plan.draw_layers:
                    if sprite.role not in ("base_back", "base_face", "base_front"):
                        layers.append((
                            sprite.stack_order, sprite.sprite_id,
                            bytes(art.images[sprite.sprite_id]),
                        ))
                selected = select_character_parts(
                    projection,
                    expression=expression, gesture=gesture,
                    talking=False,  # real voice receipts required for lip sync
                    optional_freckles=bool(
                        projection.appearance.freckles and
                        projection.appearance.freckles.casefold() not in
                        ("none", "off", "false")
                    ),
                )
                if selected.source_revision != projection.source_revision:
                    raise Avatar2DAssetError("stale character part selection")
                for sprite in load_selected_character_sprites(
                    character_root, selected,
                ):
                    layers.append((
                        _CHARACTER_STACK_ORDER[sprite.group],
                        sprite.group + "." + sprite.variant,
                        sprite.png,
                    ))
            else:
                for sprite in plan.draw_layers:
                    layers.append((
                        sprite.stack_order, sprite.sprite_id,
                        bytes(art.images[sprite.sprite_id]),
                    ))
            layers.sort(key=lambda entry: (entry[0], entry[1]))

            from tkinter import PhotoImage
            pictures = []
            for _, _, png in layers:
                image = PhotoImage(
                    data=b64encode(png).decode("ascii"), format="png",
                ).subsample(2, 2)
                pictures.append(image)
            self.canvas.delete("avatar")
            self.canvas.delete("avatar2d")
            xpos = max(85, self.canvas.winfo_width() // 2)
            for image in pictures:
                self.canvas.create_image(
                    xpos, 22 + shift, anchor="n", image=image, tags="avatar2d",
                )
            self._images = pictures
            self._last_revision = plan.presentation_revision
            fingerprint = sha256()
            fingerprint.update(plan.bundle_digest.encode())
            for _, name, png in layers:
                fingerprint.update(name.encode())
                fingerprint.update(sha256(png).digest())
            self._last_digest = fingerprint.hexdigest()
            return len(pictures), modular
        finally:
            art.close()

    def _fallback_render(self, request: AvatarRenderRequest, completed) -> None:
        self.canvas.delete("avatar2d")
        self._images.clear()
        self._last_revision = None
        self._last_digest = None
        self.fallback.render(request, completed=completed)

    def render(self, request: AvatarRenderRequest, *, completed) -> None:
        if not isinstance(request, AvatarRenderRequest):
            raise TypeError("avatar renderer requires AvatarRenderRequest")
        if not callable(completed):
            raise TypeError("completion callback required")
        self.stop()
        if not self._verified_public(request.presentation):
            self.canvas.delete("avatar")
            self.canvas.delete("avatar2d")
            self._images.clear()
            completed(
                request.decision.decision_id, False,
                "no audience-safe covered public projection available",
            )
            return
        gesture = getattr(request.decision, "gesture", None)
        frames = _gesture_frames(gesture)
        expression = _character_expression(request.decision)
        self._active_decision = request.decision.decision_id
        generation = self._generation

        def paint(index: int) -> None:
            if (
                generation != self._generation or
                self._active_decision != request.decision.decision_id
            ):
                return
            current_expression, current_gesture = _frame_character_state(
                expression=expression, gesture=gesture,
                index=index, frames=frames,
            )
            try:
                count, modular = self._paint(
                    request.presentation,
                    expression=current_expression,
                    gesture=current_gesture,
                )
                if hasattr(self.canvas, "update_idletasks"):
                    self.canvas.update_idletasks()
            except Exception:
                self._active_decision = None
                self._pending_after = None
                if index == 0:
                    self._fallback_render(request, completed)
                else:
                    self.canvas.delete("avatar2d")
                    self._images.clear()
                    completed(
                        request.decision.decision_id, False,
                        "2D modular sprite animation failed before final frame",
                    )
                return

            # A legacy static outfit has no independently animated fox parts.
            last = index + 1 >= frames or not modular
            if not last:
                self._pending_after = self.root.after(
                    90, lambda: paint(index + 1),
                )
                return
            def finish() -> None:
                self._pending_after = None
                if (
                    generation != self._generation or
                    self._active_decision != request.decision.decision_id
                ):
                    return
                self._active_decision = None
                visible = bool(
                    self.canvas.winfo_viewable()
                ) if hasattr(self.canvas, "winfo_viewable") else True
                completed(
                    request.decision.decision_id, visible,
                    (
                        f"painted {index + 1} 2D frame(s), {count} verified "
                        f"public PNG sprite layer(s) "
                        f"({'modular' if modular else 'legacy'}); "
                        f"presentation revision {request.presentation.source_revision}"
                        if visible else "avatar window not visible; no frame receipt"
                    ),
                )
            self._pending_after = self.root.after(45, finish)
        paint(0)

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
        self._generation += 1
        decision = self._active_decision
        self._active_decision = None
        if self._pending_after is not None:
            try:
                self.root.after_cancel(self._pending_after)
            except (AttributeError, ValueError):
                pass
            self._pending_after = None
        fallback_decision = self.fallback.stop()
        return decision or fallback_decision
