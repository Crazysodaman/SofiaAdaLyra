"""Fail-closed local artwork loading for public/private waist-up Avatar2D.

This is an asset boundary, NOT a renderer, a private-session issuer, an
image generator or an interaction/consent gateway. A trusted UI host must
revalidate private access before EVERY protected frame and clear its graphics
caches when access changes. This module never creates private artwork.

Private artwork bytes and manifests must live in a separately protected
local directory, not in a public Git repo, public fallback, or cloud export.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Mapping
import zlib

from sofia.social.model import PrincipalContext

from .presentation import (
    AttireMode, AudienceScope, PresentationAuthority, PresentationProjection,
)
from .private_grant import PrivatePresentationGrantResolver
from .wardrobe import LEAF_SLOTS, Layer


_SCHEMA = "sofia.avatar2d.asset_bundle.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_PNG = b"\x89PNG\r\n\x1a\n"
_MAX_MANIFEST = 65536
_MAX_IMAGE = 6 * 1024 * 1024
_MAX_TOTAL = 32 * 1024 * 1024
_MAX_LAYERS = 64
_MAX_DIMENSION = 4096
_MAX_PIXELS = 4096 * 4096


class Avatar2DAssetError(ValueError):
    """Invalid or unavailable artwork; never include private path in messages."""


def _identifier(value: object) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise Avatar2DAssetError("invalid asset identifier")
    return value


def _digest(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise Avatar2DAssetError("invalid art digest")
    return value


def _relative_png(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise Avatar2DAssetError("invalid art path")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or len(parsed.parts) < 2
        or any(part in (".", "..") for part in value.split("/"))
        or any(":" in part for part in parsed.parts)
        or parsed.suffix.lower() != ".png"
    ):
        raise Avatar2DAssetError("invalid art path")
    return parsed


def _read_file(root: Path, relpath: PurePosixPath, *, limit: int) -> bytes:
    """Reject traversal and symlinks. Root is owner-controlled local storage.

    This is a best-effort portable filesystem check, not an OS sandbox.
    Protect the directories with host ACLs against concurrent replacement.
    """
    if root.is_symlink() or not root.is_dir():
        raise Avatar2DAssetError("avatar asset root unavailable")
    root_resolved = root.resolve(strict=True)
    target = root
    for component in relpath.parts:
        target = target / component
        if target.is_symlink():
            raise Avatar2DAssetError("symlinked avatar art is disallowed")
    try:
        resolved = target.resolve(strict=True)
        if not resolved.is_relative_to(root_resolved):
            raise Avatar2DAssetError("art path escapes selected root")
        metadata = resolved.stat()
        if not stat.S_ISREG(metadata.st_mode) or not (0 < metadata.st_size <= limit):
            raise Avatar2DAssetError("art file exceeds size bounds")
        data = resolved.read_bytes()
    except (FileNotFoundError, OSError) as exc:
        raise Avatar2DAssetError("avatar art unavailable") from exc
    if not (0 < len(data) <= limit):
        raise Avatar2DAssetError("art file exceeds size bounds")
    return data


def _verify_png(data: bytes) -> None:
    """Validate bounded RGBA PNG chunk structure before passing to a decoder.

    This validates the container, CRCs, dimensions and color model, but does
    NOT replace normal renderer-side image decode limits and sandboxing.
    """
    if not data.startswith(_PNG):
        raise Avatar2DAssetError("expected PNG asset")
    pos, seen_header, seen_data, seen_end = 8, False, False, False
    while pos < len(data):
        if len(data) - pos < 12:
            raise Avatar2DAssetError("truncated PNG chunk")
        n = int.from_bytes(data[pos:pos + 4], "big")
        name = data[pos + 4:pos + 8]
        end = pos + 12 + n
        if n > _MAX_IMAGE or end > len(data):
            raise Avatar2DAssetError("invalid PNG chunk size")
        payload = data[pos + 8:pos + 8 + n]
        check = int.from_bytes(data[pos + 8 + n:end], "big")
        if zlib.crc32(name + payload) & 0xFFFFFFFF != check:
            raise Avatar2DAssetError("invalid PNG checksum")
        if not seen_header:
            if name != b"IHDR" or n != 13:
                raise Avatar2DAssetError("missing PNG header")
            width = int.from_bytes(payload[:4], "big")
            height = int.from_bytes(payload[4:8], "big")
            if (
                not 1 <= width <= _MAX_DIMENSION
                or not 1 <= height <= _MAX_DIMENSION
                or width * height > _MAX_PIXELS
                or payload[8:] != bytes((8, 6, 0, 0, 0))
            ):
                raise Avatar2DAssetError("unsupported PNG dimensions or format")
            seen_header = True
        elif name == b"IDAT":
            seen_data = True
        elif name == b"IEND":
            if n != 0 or not seen_data:
                raise Avatar2DAssetError("incomplete PNG")
            seen_end = True
            if end != len(data):
                raise Avatar2DAssetError("trailing PNG data")
            break
        elif name == b"IHDR":
            raise Avatar2DAssetError("duplicate PNG header")
        # Reject unknown critical chunks (uppercase first letter).
        elif name[:1] in (b"b", b"c", b"d", b"f", b"g", b"h", b"j", b"k",
                              b"m", b"n", b"p", b"q", b"r", b"s", b"t",
                              b"v", b"w", b"x", b"y", b"z"):
            pass  # ancillary names are validated by the image decoder
        elif name not in (b"PLTE", b"tRNS"):
            raise Avatar2DAssetError("unsupported critical PNG chunk")
        pos = end
    if not (seen_header and seen_data and seen_end):
        raise Avatar2DAssetError("incomplete PNG")


@dataclass(frozen=True, slots=True)
class Avatar2DSprite:
    """Validated artwork-to-existing-wardrobe binding.

    One sprite may cover multiple visible slots (for example a shirt may
    cover torso and both shoulders). The wardrobe remains authoritative.
    """

    sprite_id: str
    role: str  # base_back, base_body, base_face, garment, base_front, overlay
    order: int
    garment_id: str | None = None
    slots: tuple[str, ...] = ()
    wardrobe_layer: Layer | None = None


@dataclass(slots=True)
class Verified2DArtBundle:
    """Memory-scoped asset bytes; caller MUST close after use/revocation."""

    bundle_id: str
    audience: AudienceScope
    attire: AttireMode
    outfit_id: str | None
    digest: str
    images: dict[str, bytearray] = field(repr=False)
    sprites: tuple[Avatar2DSprite, ...] = ()
    _closed: bool = field(default=False, repr=False)

    def close(self) -> None:
        if not self._closed:
            for image in self.images.values():
                image[:] = b"\0" * len(image)
            self.images.clear()
            self._closed = True

    def __enter__(self) -> Verified2DArtBundle:
        if self._closed:
            raise Avatar2DAssetError("art bundle already closed")
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


@dataclass(frozen=True, slots=True)
class Avatar2DArtSelection:
    status: str  # public | private | public_fallback | unavailable
    projection: PresentationProjection
    bundle: Verified2DArtBundle | None = field(repr=False)
    reason: str


def _read_bundle(
    directory: Path,
    *,
    audience: AudienceScope,
    attire: AttireMode,
    outfit_id: str | None,
) -> Verified2DArtBundle:
    raw = _read_file(directory, PurePosixPath("manifest.json"), limit=_MAX_MANIFEST)
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise Avatar2DAssetError("invalid avatar art manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") != _SCHEMA:
        raise Avatar2DAssetError("unsupported avatar art manifest")
    if manifest.get("audience") != audience.value:
        raise Avatar2DAssetError("avatar art audience mismatch")
    if manifest.get("attire") != attire.value:
        raise Avatar2DAssetError("avatar art attire mismatch")
    if manifest.get("outfit_id") != outfit_id:
        raise Avatar2DAssetError("avatar art outfit mismatch")
    bundle_id = _identifier(manifest.get("bundle_id"))
    layers = manifest.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= _MAX_LAYERS:
        raise Avatar2DAssetError("invalid avatar art layer count")
    images: dict[str, bytearray] = {}
    sprites: list[Avatar2DSprite] = []
    seen_paths: set[str] = set()
    total = 0
    try:
        for layer in layers:
            if not isinstance(layer, dict):
                raise Avatar2DAssetError("invalid art layer")
            layer_id = _identifier(layer.get("id"))
            pathname = _relative_png(layer.get("path"))
            digest = _digest(layer.get("sha256"))
            if layer_id in images or str(pathname) in seen_paths:
                raise Avatar2DAssetError("duplicate art layer or file")
            seen_paths.add(str(pathname))
            role = layer.get("role", "base_body")
            if role not in (
                "base_back", "base_body", "base_face",
                "garment", "base_front", "overlay",
            ):
                raise Avatar2DAssetError("invalid art layer role")
            order = layer.get("order", 0)
            if type(order) is not int or not -1000 <= order <= 1000:
                raise Avatar2DAssetError("invalid art layer order")
            garment_id = layer.get("garment_id")
            slots_value = layer.get("slots", [])
            wardrobe_name = layer.get("wardrobe_layer")
            if role == "garment":
                garment_id = _identifier(garment_id)
                if (
                    not isinstance(slots_value, list)
                    or not slots_value
                    or any(type(slot) is not str or slot not in LEAF_SLOTS
                           for slot in slots_value)
                    or len(slots_value) != len(set(slots_value))
                ):
                    raise Avatar2DAssetError("invalid garment sprite slots")
                if not isinstance(wardrobe_name, str) or wardrobe_name not in Layer.__members__:
                    raise Avatar2DAssetError("invalid garment sprite layer")
                wardrobe_layer = Layer[wardrobe_name]
                slots = tuple(slots_value)
            else:
                if garment_id is not None or slots_value or wardrobe_name is not None:
                    raise Avatar2DAssetError("non-garment sprite cannot claim wardrobe")
                garment_id = None
                wardrobe_layer = None
                slots = ()
            sprites.append(
                Avatar2DSprite(
                    sprite_id=layer_id,
                    role=role,
                    order=order,
                    garment_id=garment_id,
                    slots=slots,
                    wardrobe_layer=wardrobe_layer,
                )
            )
            payload = _read_file(directory, pathname, limit=_MAX_IMAGE)
            if sha256(payload).hexdigest() != digest:
                raise Avatar2DAssetError("art layer checksum mismatch")
            _verify_png(payload)
            total += len(payload)
            if total > _MAX_TOTAL:
                raise Avatar2DAssetError("art bundle exceeds memory budget")
            images[layer_id] = bytearray(payload)
    except BaseException:
        for data in images.values():
            data[:] = b"\0" * len(data)
        raise
    return Verified2DArtBundle(
        bundle_id=bundle_id,
        audience=audience,
        attire=attire,
        outfit_id=outfit_id,
        digest=sha256(raw).hexdigest(),
        images=images,
        sprites=tuple(sprites),
    )


class Avatar2DAssetGateway:
    """Trusted UI loader, always exposing safe public fallback on failure.

    No persistence, asset generation, network access, thumbnail caching or
    private permissions are created. A private session must be reauthorized
    and the returned bundle must be discarded if the next frame is no longer
    authorized. This loader is not yet wired to the live desktop renderer.
    """

    def __init__(
        self,
        *,
        authority: PresentationAuthority,
        grant_resolver: PrivatePresentationGrantResolver,
        public_root: Path,
        private_root: Path,
    ) -> None:
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("canonical presentation authority required")
        if not isinstance(grant_resolver, PrivatePresentationGrantResolver):
            raise TypeError("existing SAFE private grant resolver required")
        if not isinstance(public_root, Path) or not isinstance(private_root, Path):
            raise TypeError("explicit public and private asset roots required")
        public = public_root.resolve()
        private = private_root.resolve()
        if private == public or private.is_relative_to(public) or public.is_relative_to(private):
            raise ValueError("private artwork needs a separate asset root")
        self._authority = authority
        self._resolver = grant_resolver
        self._public_root = public_root
        self._private_root = private_root

    def public(self, *, fallback: bool = False) -> Avatar2DArtSelection:
        projection = self._authority.projection(AudienceScope.PUBLIC)
        # New generated wardrobe packs live at outfits/<canonical ID>.
        # Retain the older single-pack root as a verified compatibility path,
        # but never scan unknown art directories or take a private asset.
        roots = []
        if projection.outfit_id:
            try:
                roots.append(
                    self._public_root / "outfits" / _identifier(projection.outfit_id)
                )
            except Avatar2DAssetError:
                return Avatar2DArtSelection(
                    "unavailable", projection, None, "approved public artwork unavailable"
                )
        roots.append(self._public_root)
        bundle = None
        for root in roots:
            try:
                bundle = _read_bundle(
                    root,
                    audience=AudienceScope.PUBLIC,
                    attire=AttireMode.CLOTHED,
                    outfit_id=projection.outfit_id,
                )
                break
            except (Avatar2DAssetError, OSError):
                continue
        if bundle is None:
            return Avatar2DArtSelection(
                "unavailable", projection, None, "approved public artwork unavailable"
            )
        return Avatar2DArtSelection(
            "public_fallback" if fallback else "public",
            projection, bundle,
            "covered public presentation" if fallback else "public presentation",
        )

    def _verified_grant(
        self, *,
        principal: PrincipalContext | None,
        explicit_current_opt_in: bool,
    ):
        # Permission-store corruption, missing STOP evidence and unexpected
        # host errors must revoke visibility, not preserve cached private art.
        try:
            return self._resolver.resolve(
                principal=principal,
                explicit_current_opt_in=explicit_current_opt_in,
            )
        except Exception:
            return None

    def private(
        self,
        *,
        principal: PrincipalContext | None,
        explicit_current_opt_in: bool,
    ) -> Avatar2DArtSelection:
        grant = self._verified_grant(
            principal=principal,
            explicit_current_opt_in=explicit_current_opt_in,
        )
        if grant is None:
            return self.public(fallback=True)
        current = self._authority.current
        if not current.private_only:
            return self.public(fallback=True)
        revision = current.revision
        projection = self._authority.projection(AudienceScope.PRIVATE, grant=grant)
        if projection.private_fallback_used or projection.source_revision != revision:
            return self.public(fallback=True)

        if projection.attire is AttireMode.NUDE:
            private_dir = self._private_root / "nude"
        elif projection.outfit_id is not None:
            private_dir = self._private_root / "outfits" / _identifier(projection.outfit_id)
        else:
            return self.public(fallback=True)
        try:
            bundle = _read_bundle(
                private_dir,
                audience=AudienceScope.PRIVATE,
                attire=projection.attire,
                outfit_id=projection.outfit_id,
            )
        except (Avatar2DAssetError, OSError):
            return self.public(fallback=True)

        # Reject mutations/revocation that happen while the private asset is
        # read. The actual renderer MUST repeat this check before each frame.
        if (
            self._authority.current.revision != revision
            or self._verified_grant(
                principal=principal,
                explicit_current_opt_in=explicit_current_opt_in,
            ) is None
        ):
            bundle.close()
            return self.public(fallback=True)
        return Avatar2DArtSelection(
            "private", projection, bundle, "authorized private presentation"
        )

    def private_still_authorized(
        self,
        selection: Avatar2DArtSelection,
        *,
        principal: PrincipalContext | None,
        explicit_current_opt_in: bool,
    ) -> bool:
        """Run immediately before each protected frame; clear on revocation."""
        if selection.status != "private" or selection.bundle is None:
            return False
        valid = (
            not selection.bundle._closed
            and self._authority.current.private_only
            and self._authority.current.revision == selection.projection.source_revision
            and self._verified_grant(
                principal=principal,
                explicit_current_opt_in=explicit_current_opt_in,
            ) is not None
        )
        if not valid:
            selection.bundle.close()
        return valid
