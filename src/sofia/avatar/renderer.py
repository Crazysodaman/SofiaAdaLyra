"""Renderer boundary that distinguishes requested from actually rendered state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import re

from sofia.avatar.assets import AvatarAsset

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RenderRequest:
    request_id: str
    presentation_digest: str
    assets: tuple[AvatarAsset, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise ValueError("request_id required")
        if not isinstance(self.presentation_digest, str) or _DIGEST.fullmatch(
            self.presentation_digest
        ) is None:
            raise ValueError("presentation_digest must be lowercase SHA-256")
        if not isinstance(self.assets, tuple) or any(
            not isinstance(item, AvatarAsset) for item in self.assets
        ):
            raise TypeError("assets must be a tuple of AvatarAsset")


@dataclass(frozen=True, slots=True)
class RenderReceipt:
    request_id: str
    renderer_id: str
    rendered_at: datetime
    presentation_digest: str
    frame_digest: str

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.renderer_id.strip():
            raise ValueError("request_id and renderer_id required")
        if self.rendered_at.tzinfo is None or self.rendered_at.utcoffset() is None:
            raise ValueError("rendered_at must be timezone-aware")
        for label, value in (
            ("presentation_digest", self.presentation_digest),
            ("frame_digest", self.frame_digest),
        ):
            if _DIGEST.fullmatch(value) is None:
                raise ValueError(f"{label} must be lowercase SHA-256")


class AvatarRenderer(ABC):
    @abstractmethod
    def render(self, request: RenderRequest) -> RenderReceipt:
        """Return a receipt only after the renderer actually produced a frame."""
        raise NotImplementedError
