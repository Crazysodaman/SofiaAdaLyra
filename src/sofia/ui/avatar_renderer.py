"""Optional lightweight Tk avatar renderer with explicit frame acknowledgement."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sofia.platform.application.expression_runtime import ExpressionDecision
from sofia.avatar.presentation import PresentationProjection
from sofia.voice.prosody_matrix import VoiceProsodyProfile


_COLOR_FALLBACKS = {
    "deep crimson": "#8B1E3F",
    "dark violet": "#3A245C",
    "warm ivory": "#F1E9D8",
    "violet": "#8F5BDB",
    "purple": "#8F5BDB",
}


@dataclass(frozen=True, slots=True)
class AvatarRenderRequest:
    decision: ExpressionDecision
    presentation: PresentationProjection


class TkAvatarRenderer:
    """Render acknowledged symbolic frames; never claims unpainted animation."""

    backend_name = "tk-canvas-avatar-v1"

    def __init__(self, *, root, canvas) -> None:
        self.root = root
        self.canvas = canvas
        self._generation = 0
        self._pending: dict[int, object] = {}
        self._active_decision_id: str | None = None

    @staticmethod
    def _color(value: str, fallback: str) -> str:
        if value.startswith("#") and len(value) == 7:
            return value
        return _COLOR_FALLBACKS.get(value.casefold(), fallback)

    def stop(self) -> str | None:
        self._generation += 1
        for handle in tuple(self._pending.values()):
            try:
                self.root.after_cancel(handle)
            except Exception:
                pass
        self._pending.clear()
        previous = self._active_decision_id
        self._active_decision_id = None
        return previous

    def render(
        self, request: AvatarRenderRequest, *,
        completed: Callable[[str, bool, str], None],
    ) -> None:
        if not isinstance(request, AvatarRenderRequest):
            raise TypeError("AvatarRenderRequest required")
        if not callable(completed):
            raise TypeError("completion callback required")
        self.stop()
        self._active_decision_id = request.decision.decision_id
        self._generation += 1
        generation = self._generation
        avatar = request.decision.avatar_state
        gesture = request.decision.gesture or "still"
        rendered_components = tuple(dict.fromkeys(
            item for item in (
                None if avatar is None else avatar.face,
                None if avatar is None else avatar.gaze,
                None if avatar is None else avatar.ears,
                None if avatar is None else avatar.tail,
                request.decision.pose,
                gesture,
            )
            if item is not None
        ))
        animated = () if avatar is None else (avatar.ears, avatar.tail)
        frames = 5 if any(
            item is not None and item.startswith(("tail-", "ear-", "slow-tail"))
            for item in animated
        ) or gesture.startswith(("tail-", "ear-", "slow-tail")) or request.decision.pose == "walk" else 2

        def paint(index: int) -> None:
            if generation != self._generation:
                return
            try:
                self._draw(request, index=index, frames=frames)
                self.canvas.update_idletasks()
            except Exception as exc:
                self._active_decision_id = None
                self._pending.clear()
                completed(
                    request.decision.decision_id, False,
                    f"{type(exc).__name__}: {exc}",
                )
                return
            if index + 1 >= frames:
                self._active_decision_id = None
                self._pending.clear()
                completed(
                    request.decision.decision_id, True,
                    f"rendered {frames} visible frame(s): "
                    + ", ".join(rendered_components or ("still",)),
                )
                return
            handle = self.root.after(90, lambda: paint(index + 1))
            self._pending[index] = handle

        paint(0)

    def render_idle(self, presentation: PresentationProjection) -> None:
        """Paint a quiet canonical pose without manufacturing a turn receipt."""
        placeholder = ExpressionDecision(
            decision_id="idle", message_id="idle", session_id="idle",
            principal_id="system", audience_id="public", intent="idle",
            text_sha256="0" * 64, emotion_labels=(), emotion_evidence_refs=(),
            prosody=VoiceProsodyProfile(),
            gesture=None, pose="stand-relaxed", intensity="subtle",
            presentation_revision=presentation.source_revision,
            created_at=datetime.now(timezone.utc),
        )
        self._draw(AvatarRenderRequest(placeholder, presentation), index=0, frames=1)

    def _draw(self, request: AvatarRenderRequest, *, index: int, frames: int) -> None:
        decision, presentation = request.decision, request.presentation
        avatar = decision.avatar_state
        self.canvas.delete("avatar")
        width = max(240, int(self.canvas.winfo_width()))
        height = max(280, int(self.canvas.winfo_height()))
        hair = self._color(presentation.appearance.hair_color, "#8B1E3F")
        tail = self._color(presentation.appearance.tail_color, "#3A245C")
        skin = "#F1E9D8"
        accent = "#19D3C5"
        eyes = self._color(presentation.appearance.eye_color or "violet", "#8F5BDB")
        pose = decision.pose
        if pose == "stand-relaxed" and presentation.appearance.posture in {
            "recline", "lean-forward", "hip-pop", "hands-behind-back",
            "sit-cross-legged", "stretch", "walk",
        }:
            pose = presentation.appearance.posture
        phase = -1 if index % 2 else 1
        lean = 12 if pose == "lean-forward" else 0
        if pose == "recline":
            lean = -12
        elif pose == "hip-pop":
            lean = 8
        center = width // 2 + lean
        ears = decision.gesture if avatar is None else avatar.ears
        tail_cue = decision.gesture if avatar is None else avatar.tail
        gaze_cue = decision.gesture if avatar is None else avatar.gaze
        face_cue = decision.gesture if avatar is None else avatar.face
        ear_shift = 9 * phase if ears in {"ear-flick", "ear-perk"} else 0
        ear_flat = 20 if ears == "ear-flatten" or presentation.appearance.ear_pose == "flattened" else 0
        if presentation.appearance.tail_pose == "raised":
            tail_lift = 20
        elif presentation.appearance.tail_pose == "lowered":
            tail_lift = -20
        else:
            tail_lift = 0
        tail_shift = (
            24 * phase
            if tail_cue in {"tail-swish", "slow-tail-sway"}
            else 0
        )

        # Tail is deliberately behind the body.
        self.canvas.create_line(
            center + 40, height - 70, center + 92 + tail_shift, height - 112,
            center + 78 - tail_shift // 2, height - 155 - tail_lift,
            fill=tail, width=18, smooth=True, capstyle="round", tags="avatar",
        )
        torso_shift = 10 if pose == "hip-pop" else 0
        self.canvas.create_polygon(
            center - 38, 184, center + 38, 184,
            center + 56 + torso_shift, height - 38,
            center - 52 + torso_shift, height - 38,
            fill="#171A21", outline=accent, width=2, tags="avatar",
        )
        if pose == "hands-behind-back":
            self.canvas.create_line(
                center - 35, 205, center, 235, center + 35, 205,
                fill=skin, width=7, smooth=True, tags="avatar",
            )
        elif pose == "sit-cross-legged":
            self.canvas.create_line(
                center - 46, height - 50, center + 42, height - 32,
                fill="#0B0D12", width=14, capstyle="round", tags="avatar",
            )
            self.canvas.create_line(
                center + 46, height - 50, center - 42, height - 32,
                fill="#0B0D12", width=14, capstyle="round", tags="avatar",
            )
        elif pose == "stretch":
            self.canvas.create_line(
                center - 38, 192, center - 66, 126,
                fill=skin, width=8, tags="avatar",
            )
            self.canvas.create_line(
                center + 38, 192, center + 66, 126,
                fill=skin, width=8, tags="avatar",
            )
        elif pose == "walk":
            self.canvas.create_line(
                center - 18, height - 70, center - 35 + 10 * phase, height - 30,
                fill="#0B0D12", width=12, tags="avatar",
            )
            self.canvas.create_line(
                center + 18, height - 70, center + 35 - 10 * phase, height - 30,
                fill="#0B0D12", width=12, tags="avatar",
            )
        self.canvas.create_oval(
            center - 55, 92, center + 55, 202,
            fill=skin, outline=accent, width=2, tags="avatar",
        )
        # Lightweight frame-dependent hair sway, not a rigged strand simulation.
        hair_sway = (5 * phase if frames > 1 else 0)
        self.canvas.create_line(
            center - 47, 111, center - 55 + hair_sway, 179,
            fill=hair, width=9, smooth=True, tags="avatar",
        )
        self.canvas.create_line(
            center + 47, 111, center + 55 + hair_sway, 179,
            fill=hair, width=9, smooth=True, tags="avatar",
        )
        self.canvas.create_arc(
            center - 60, 78, center + 60, 188,
            start=0, extent=180, fill=hair, outline=hair, tags="avatar",
        )
        self.canvas.create_polygon(
            center - 48, 98 + ear_flat, center - 34 + ear_shift, 35 + ear_flat,
            center - 10, 92, fill=hair, outline=accent, tags="avatar",
        )
        self.canvas.create_polygon(
            center + 10, 92, center + 34 - ear_shift, 35 + ear_flat,
            center + 48, 98 + ear_flat, fill=hair, outline=accent, tags="avatar",
        )
        gaze = 4 if gaze_cue in {"sultry-gaze", "avert-gaze", "look-back"} else 0
        blink = (face_cue == "blink" or decision.gesture == "blink" or (frames > 2 and index == frames // 2))
        if blink:
            self.canvas.create_line(center - 29, 134, center - 14, 134, fill="#25202D", width=2, tags="avatar")
            self.canvas.create_line(center + 14, 134, center + 29, 134, fill="#25202D", width=2, tags="avatar")
        else:
            self.canvas.create_oval(center - 28, 126, center - 14, 139, fill="#FFFFFF", tags="avatar")
            self.canvas.create_oval(center + 14, 126, center + 28, 139, fill="#FFFFFF", tags="avatar")
            self.canvas.create_oval(center - 22 + gaze, 129, center - 17 + gaze, 136, fill=eyes, tags="avatar")
            self.canvas.create_oval(center + 20 + gaze, 129, center + 25 + gaze, 136, fill=eyes, tags="avatar")
            self.canvas.create_oval(center - 21 + gaze, 131, center - 19 + gaze, 135, fill="#15121E", tags="avatar")
            self.canvas.create_oval(center + 21 + gaze, 131, center + 23 + gaze, 135, fill="#15121E", tags="avatar")
        if presentation.appearance.freckles and presentation.appearance.freckles != "none":
            for dx in (-35, -30, -25, 25, 30, 35):
                self.canvas.create_oval(
                    center + dx - 1, 148, center + dx + 1, 150,
                    fill="#B97878", outline="", tags="avatar",
                )
        if presentation.appearance.piercings:
            self.canvas.create_oval(
                center - 38, 74, center - 33, 79,
                fill="#B8CBD6", outline="", tags="avatar",
            )
        if presentation.appearance.tattoos:
            self.canvas.create_text(
                center + 26, 228, text="✧", fill="#A58AC6",
                font=("Segoe UI", 14), tags="avatar",
            )
        if face_cue == "blush" or decision.gesture == "blush":
            self.canvas.create_oval(center - 43, 148, center - 27, 156, fill="#E8A0A8", outline="", tags="avatar")
            self.canvas.create_oval(center + 27, 148, center + 43, 156, fill="#E8A0A8", outline="", tags="avatar")
        frown = face_cue == "frown" or ears == "ear-flatten" or presentation.appearance.expression == "frown"
        mouth = "︶" if frown else "⌣"
        self.canvas.create_text(center, 164, text=mouth, fill="#171A21", font=("Segoe UI", 17), tags="avatar")
        outfit = presentation.outfit_id or "canonical presentation"
        self.canvas.create_text(
            center, height - 18,
            text=f"{outfit} · {decision.gesture or 'intentional stillness'}",
            fill=accent, font=("Segoe UI", 9), tags="avatar",
        )
