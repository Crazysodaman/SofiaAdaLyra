"""Pure, pose-aware hit testing for *rendered* 2D avatar layers.

The render host owns authentication, frame provenance, session state and
interaction policy. This module performs geometry resolution ONLY. It never
decides consent, simulates a touch, sends a chat message or invokes an LLM.

A real UI must supply per-frame transforms and alpha masks from its actual
visible artwork. Synthesized/declared body regions without rendered pixels are
not clickable.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Mapping

from sofia.modules.avatar.presentation import AudienceScope, PrivatePresentationGrant
from sofia.modules.interaction.core import Region


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_DIGEST = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MAX_ALPHA_PIXELS = 1024 * 1024
_MAX_FRAME_ALPHA_PIXELS = 16 * 1024 * 1024


def _finite(number: object, label: str) -> float:
    if type(number) not in (float, int) or not isfinite(number):
        raise ValueError(f"{label} must be finite")
    return float(number)


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


@dataclass(frozen=True, slots=True)
class LayerTransform:
    """Local sprite unit square -> *actual rendered* normalized viewport.

    Local coordinates (0..1) are the alpha mask's image coordinates. This
    invertible affine transform handles translation, scaling, rotation and
    horizontal mirroring. The renderer must pass the final painted transform,
    not a manifest default or a cached pre-animation pose.
    """

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 0.0
    e: float = 1.0
    f: float = 0.0

    def __post_init__(self) -> None:
        for label in ("a", "b", "c", "d", "e", "f"):
            _finite(getattr(self, label), label)
        if abs(self.a * self.e - self.b * self.d) < 1e-9:
            raise ValueError("sprite transform must be invertible")

    def to_local(self, x: float, y: float) -> tuple[float, float]:
        det = self.a * self.e - self.b * self.d
        dx, dy = x - self.c, y - self.f
        return (
            (self.e * dx - self.b * dy) / det,
            (-self.d * dx + self.a * dy) / det,
        )


@dataclass(frozen=True, slots=True)
class RenderedHitLayer:
    """One visible composited sprite, including its alpha mask and target.

    garment_id identifies what was clicked when an outfit layer covers a body
    region. This is not permission to infer contact with the skin underneath.
    """

    layer_id: str
    region_id: str
    z_index: int
    mask_width: int
    mask_height: int
    alpha_mask: bytes
    transform: LayerTransform
    audience: AudienceScope = AudienceScope.PUBLIC
    garment_id: str | None = None

    def __post_init__(self) -> None:
        _id(self.layer_id, "layer ID")
        _id(self.region_id, "region ID")
        if self.garment_id is not None:
            _id(self.garment_id, "garment ID")
        if type(self.z_index) is not int:
            raise TypeError("z_index must be integer")
        if type(self.mask_width) is not int or type(self.mask_height) is not int:
            raise TypeError("alpha dimensions must be integers")
        if not (1 <= self.mask_width <= 1024 and 1 <= self.mask_height <= 1024):
            raise ValueError("alpha dimensions out of bounds")
        if self.mask_width * self.mask_height > _MAX_ALPHA_PIXELS:
            raise ValueError("alpha mask too large")
        if not isinstance(self.alpha_mask, bytes) or (
            len(self.alpha_mask) != self.mask_width * self.mask_height
        ):
            raise ValueError("alpha mask dimensions do not match bytes")
        if not isinstance(self.transform, LayerTransform):
            raise TypeError("sprite transform required")
        if not isinstance(self.audience, AudienceScope):
            raise TypeError("layer audience must be an AudienceScope")

    def opaque_at(self, viewport_x: float, viewport_y: float) -> bool:
        u, v = self.transform.to_local(viewport_x, viewport_y)
        if not (0.0 <= u < 1.0 and 0.0 <= v < 1.0):
            return False
        column = min(int(u * self.mask_width), self.mask_width - 1)
        row = min(int(v * self.mask_height), self.mask_height - 1)
        return self.alpha_mask[row * self.mask_width + column] >= 160


@dataclass(frozen=True, slots=True)
class RenderedHitFrame:
    """Frame exactness prevents clicks on a stale or occluded body region."""

    frame_id: str
    presentation_revision: int
    bundle_digest: str
    audience: AudienceScope
    layers: tuple[RenderedHitLayer, ...]

    def __post_init__(self) -> None:
        _id(self.frame_id, "frame ID")
        if type(self.presentation_revision) is not int or self.presentation_revision <= 0:
            raise ValueError("positive presentation revision required")
        if not isinstance(self.bundle_digest, str) or (
            _DIGEST.fullmatch(self.bundle_digest) is None
        ):
            raise ValueError("validated asset bundle digest required")
        if not isinstance(self.audience, AudienceScope):
            raise TypeError("frame audience required")
        if not isinstance(self.layers, tuple) or len(self.layers) > 128:
            raise ValueError("too many hit layers")
        names: set[str] = set()
        total = 0
        for layer in self.layers:
            if not isinstance(layer, RenderedHitLayer):
                raise TypeError("frame contains invalid layer")
            if layer.layer_id in names:
                raise ValueError("duplicate layer ID")
            names.add(layer.layer_id)
            total += len(layer.alpha_mask)
            if self.audience is AudienceScope.PUBLIC and (
                layer.audience is not AudienceScope.PUBLIC
            ):
                raise ValueError("private layer cannot enter a public hit frame")
        if total > _MAX_FRAME_ALPHA_PIXELS:
            raise ValueError("frame masks exceed memory bound")


@dataclass(frozen=True, slots=True)
class AvatarHitResult:
    """Only 'hit' with a region ID can become candidate virtual UI evidence."""

    status: str  # hit | miss | stale | restricted
    region_id: str | None = None
    layer_id: str | None = None
    garment_id: str | None = None
    visual_frame_id: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("hit", "miss", "stale", "restricted"):
            raise ValueError("invalid hit status")
        if self.status != "hit" and (
            self.region_id is not None
            or self.layer_id is not None
            or self.garment_id is not None
        ):
            raise ValueError("non-hit results must not expose region details")


def hit_test_avatar(
    frame: RenderedHitFrame,
    *,
    viewport_x: float,
    viewport_y: float,
    expected_frame_id: str,
    expected_revision: int,
    canonical_regions: Mapping[str, Region],
    private_grant: PrivatePresentationGrant | None = None,
) -> AvatarHitResult:
    """Resolve the top *painted opaque* layer to a canonical region.

    An authenticated application host must independently authenticate the UI
    actor, resolve any grant from SAFE, check interaction session STOP/consent,
    and establish that the frame really is the displayed one. This function
    is NOT an authorization endpoint or a completed virtual-touch record.

    A private result never exposes a region unless the caller supplies a
    previously trusted and still valid grant AND the frame has private scope.
    """
    if not isinstance(frame, RenderedHitFrame):
        raise TypeError("rendered frame required")
    if not isinstance(canonical_regions, Mapping):
        raise TypeError("canonical region mapping required")
    x = _finite(viewport_x, "viewport_x")
    y = _finite(viewport_y, "viewport_y")
    if not isinstance(expected_frame_id, str):
        raise TypeError("expected frame ID must be text")
    if type(expected_revision) is not int:
        raise TypeError("expected revision must be integer")
    if frame.frame_id != expected_frame_id or frame.presentation_revision != expected_revision:
        return AvatarHitResult("stale")
    if not (0.0 <= x < 1.0 and 0.0 <= y < 1.0):
        return AvatarHitResult("miss")

    # Both the visual layer and canonical region gate MUST authorize a private
    # region. Do not expose layer IDs/region IDs when unauthenticated.
    for layer in sorted(frame.layers, key=lambda item: item.z_index, reverse=True):
        if not layer.opaque_at(x, y):
            continue
        region = canonical_regions.get(layer.region_id)
        if region is None or not isinstance(region, Region):
            return AvatarHitResult("miss")
        sensitive = layer.audience is AudienceScope.PRIVATE or region.private
        if sensitive:
            if frame.audience is not AudienceScope.PRIVATE or not isinstance(
                private_grant, PrivatePresentationGrant
            ):
                return AvatarHitResult("restricted")
            try:
                private_grant.require()
            except PermissionError:
                return AvatarHitResult("restricted")
        return AvatarHitResult(
            "hit",
            region_id=region.id,
            layer_id=layer.layer_id,
            garment_id=layer.garment_id,
            visual_frame_id=frame.frame_id,
        )
    return AvatarHitResult("miss")
