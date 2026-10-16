"""Verified 3D avatar driver interface, separate from the 2D animation rig.

An installed 3D model/driver must explicitly satisfy this contract. The
adapter will NOT generate a placeholder 3D avatar, auto-launch a game engine
or claim a rendered frame without a real driver callback.

Semantic gestures and wardrobe IDs are shared with 2D; bone tracks,
blendshapes, cloth physics and mesh assets belong solely to the 3D driver.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Callable, Protocol, runtime_checkable

from sofia.avatar.presentation import AttireMode, AudienceScope, PresentationProjection
from sofia.ui.avatar_renderer import AvatarRenderRequest


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


@dataclass(frozen=True, slots=True)
class Avatar3DRig:
    """An installed, verified model's semantic animation bindings."""

    model_id: str
    model_sha256: str
    rig_id: str
    supported_gestures: frozenset[str]
    supported_poses: frozenset[str]

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.model_id) or not _ID.fullmatch(self.rig_id):
            raise ValueError("valid rig/model ID required")
        if not _DIGEST.fullmatch(self.model_sha256):
            raise ValueError("verified 3D model digest required")
        if (
            not isinstance(self.supported_gestures, frozenset)
            or not isinstance(self.supported_poses, frozenset)
            or any(not isinstance(value, str) or not _ID.fullmatch(value)
                   for value in (*self.supported_gestures, *self.supported_poses))
        ):
            raise ValueError("invalid 3D animation bindings")


@dataclass(frozen=True, slots=True)
class Avatar3DAnimationCue:
    """Mode-agnostic expression projected into the separately rigged 3D host."""

    decision_id: str
    presentation_revision: int
    outfit_id: str
    garment_ids: tuple[str, ...]
    gesture: str | None
    pose: str | None
    intensity: str
    emotion_labels: tuple[str, ...]
    model_sha256: str


@runtime_checkable
class VerifiedAvatar3DDriver(Protocol):
    """External realtime renderer. It must own a real verified 3D rig."""

    def ready(self, rig: Avatar3DRig) -> bool: ...
    def render(
        self, cue: Avatar3DAnimationCue, *,
        completed: Callable[[str, bool, str], None],
    ) -> None: ...
    def render_idle(self, projection: PresentationProjection) -> None: ...
    def stop(self) -> str | None: ...


class Avatar3DRenderer:
    """3D adapter with separate animation rig and no fabricated success."""

    backend_name = "verified-external-3d-avatar-v1"

    def __init__(self, *, rig: Avatar3DRig, driver: VerifiedAvatar3DDriver):
        if not isinstance(rig, Avatar3DRig):
            raise TypeError("actual validated 3D rig required")
        if not isinstance(driver, VerifiedAvatar3DDriver) or driver.ready(rig) is not True:
            raise RuntimeError("verified 3D renderer and installed model unavailable")
        self._rig = rig
        self._driver = driver
        self._generation = 0
        self._active_decision: str | None = None

    def stop(self) -> str | None:
        self._generation += 1
        prior = self._active_decision
        self._active_decision = None
        # Host owns the GPU rig and MUST stop its simulation on this call.
        stopped = self._driver.stop()
        return prior or stopped

    def render(self, request: AvatarRenderRequest, *, completed) -> None:
        if not isinstance(request, AvatarRenderRequest):
            raise TypeError("trusted AvatarRenderRequest required")
        if not callable(completed):
            raise TypeError("completion callback required")
        projection = request.presentation
        decision = request.decision
        if (
            projection.audience is not AudienceScope.PUBLIC
            or projection.attire is not AttireMode.CLOTHED
            or projection.outfit_id is None
        ):
            completed(decision.decision_id, False, "3D public model denies private content")
            return
        if decision.presentation_revision != projection.source_revision:
            completed(decision.decision_id, False, "stale 3D appearance revision")
            return
        self.stop()
        gesture = decision.gesture
        pose = decision.pose
        if gesture is not None and gesture not in self._rig.supported_gestures:
            gesture = None  # Unknown rig animations are never invented.
        if pose is not None and pose not in self._rig.supported_poses:
            pose = None
        cue = Avatar3DAnimationCue(
            decision_id=decision.decision_id,
            presentation_revision=projection.source_revision,
            outfit_id=projection.outfit_id,
            garment_ids=projection.item_ids,
            gesture=gesture,
            pose=pose,
            intensity=decision.intensity,
            emotion_labels=decision.emotion_labels,
            model_sha256=self._rig.model_sha256,
        )
        self._active_decision = decision.decision_id
        generation = self._generation
        def real_frame(decision_id: str, visible: bool, detail: str) -> None:
            if (
                generation != self._generation
                or decision_id != self._active_decision
            ):
                return
            self._active_decision = None
            # No result is embellished: the driver controls actual display
            # truth. A render request without a frame callback is pending.
            if type(visible) is not bool:
                completed(decision_id, False, "invalid 3D driver receipt")
            else:
                completed(decision_id, visible, detail)
        try:
            self._driver.render(cue, completed=real_frame)
        except Exception as exc:
            self._active_decision = None
            completed(decision.decision_id, False, f"3D driver failed: {type(exc).__name__}")

    def render_idle(self, projection: PresentationProjection) -> None:
        self.stop()
        if (
            projection.audience is AudienceScope.PUBLIC
            and projection.attire is AttireMode.CLOTHED
            and projection.outfit_id is not None
        ):
            self._driver.render_idle(projection)
