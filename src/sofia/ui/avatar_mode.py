"""Exclusive 2D/3D avatar backend selection, separate from Sofía identity.

Both backends consume the same trusted AvatarRenderRequest and publish actual
output receipts. Only one renderer is active; switching cancels in-flight
frames and prevents an old renderer's late callback from being accepted.

No 3D driver/model is inferred from a setting. Unavailable modes fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol, runtime_checkable

from sofia.avatar.presentation import PresentationProjection
from sofia.ui.avatar_renderer import AvatarRenderRequest


class AvatarVisualMode(str, Enum):
    TWO_D = "2d"
    THREE_D = "3d"


class AvatarModeUnavailable(RuntimeError):
    pass


@runtime_checkable
class AvatarBackend(Protocol):
    backend_name: str

    def stop(self) -> str | None: ...
    def render(
        self,
        request: AvatarRenderRequest,
        *,
        completed: Callable[[str, bool, str], None],
    ) -> None: ...
    def render_idle(self, presentation: PresentationProjection) -> None: ...


@dataclass(frozen=True, slots=True)
class AvatarModeTransition:
    previous: AvatarVisualMode
    active: AvatarVisualMode
    changed: bool
    cancelled_decision_id: str | None
    cancelled_backend: str | None


class ExclusiveAvatarRenderer:
    """One visual owner and one animation pipeline at any instant.

    A backend must report only *really displayed* frames. This coordinator
    does not create or validate presentation grants and never changes
    canonical appearance, wardrobe or emotion state.
    """

    def __init__(
        self,
        *,
        two_d: AvatarBackend,
        three_d: AvatarBackend | None = None,
        preferred: AvatarVisualMode = AvatarVisualMode.TWO_D,
        clear_visual: Callable[[], None] | None = None,
    ) -> None:
        if not isinstance(two_d, AvatarBackend):
            raise TypeError("functional 2D backend required")
        if three_d is not None and not isinstance(three_d, AvatarBackend):
            raise TypeError("3D backend must implement avatar render contract")
        if three_d is two_d:
            raise ValueError("2D and 3D must be different renderer instances")
        if not isinstance(preferred, AvatarVisualMode):
            raise ValueError("invalid avatar visual mode")
        self._backends: dict[AvatarVisualMode, AvatarBackend] = {
            AvatarVisualMode.TWO_D: two_d,
        }
        if three_d is not None:
            self._backends[AvatarVisualMode.THREE_D] = three_d
        self._active = AvatarVisualMode.TWO_D
        self._generation = 0
        self._clear_visual = clear_visual or (lambda: None)
        if preferred is AvatarVisualMode.THREE_D:
            self.select(preferred)

    @property
    def active_mode(self) -> AvatarVisualMode:
        return self._active

    @property
    def available_modes(self) -> tuple[AvatarVisualMode, ...]:
        return tuple(self._backends)

    @property
    def backend_name(self) -> str:
        return self._backends[self._active].backend_name

    def select(self, mode: AvatarVisualMode) -> AvatarModeTransition:
        if not isinstance(mode, AvatarVisualMode):
            raise ValueError("unsupported visual mode")
        if mode not in self._backends:
            raise AvatarModeUnavailable(
                "3D is not installed or verified on this host"
                if mode is AvatarVisualMode.THREE_D
                else "requested avatar renderer is unavailable"
            )
        if mode is self._active:
            return AvatarModeTransition(mode, mode, False, None, None)
        old = self._backends[self._active]
        previous = self._active
        # Invalidate callbacks BEFORE stopping animation. Stop itself may
        # re-enter the event loop on some platform drivers.
        self._generation += 1
        cancelled = old.stop()
        # Clear old backend pixels before any newly selected mode may paint.
        # The renderer-specific stop() must also release its GPU/animation
        # resources; the UI clear handles shared Tk preview contents.
        self._clear_visual()
        self._active = mode
        return AvatarModeTransition(
            previous, mode, True, cancelled, old.backend_name,
        )

    def render(
        self,
        request: AvatarRenderRequest,
        *,
        completed: Callable[[str, bool, str], None],
    ) -> None:
        if not isinstance(request, AvatarRenderRequest):
            raise TypeError("trusted AvatarRenderRequest required")
        if not callable(completed):
            raise TypeError("completion callback required")
        backend = self._backends[self._active]
        self._generation += 1
        generation = self._generation
        mode = self._active
        # A callback from a replaced renderer cannot record a fake
        # successful receipt after the owner has switched modes.
        def guarded(decision_id: str, rendered: bool, detail: str) -> None:
            if generation == self._generation and mode is self._active:
                completed(decision_id, rendered, detail)
        backend.render(request, completed=guarded)

    def render_idle(self, presentation: PresentationProjection) -> None:
        self._backends[self._active].render_idle(presentation)

    def stop(self) -> str | None:
        self._generation += 1
        return self._backends[self._active].stop()
