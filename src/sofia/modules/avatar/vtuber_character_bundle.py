"""Verified public modular character-art packs for the waist-up Tk renderer.

A pack is **optional**. It substitutes face/hair/fox sprites for the legacy
all-in-one base layers, never superimposes two bodies or two fox tails.

The manifest is untrusted art metadata, not presentation/owner authority.
Only checked local PNGs from the configured public art directory can enter
the compositing plan. Private assets are never discovered by this loader.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from .vtuber_asset_bundle import (
    Avatar2DAssetError, _read_file, _relative_png, _verify_png,
)
from .vtuber_character_parts import (
    _ANCHOR, _PUBLIC_GROUPS, _Z,
)
from .vtuber_character_selection import CharacterPartSelection


_SCHEMA = "sofia.avatar2d.character_parts.v1"
_MAX_MANIFEST_BYTES = 65536
_MAX_PNG_BYTES = 6 * 1024 * 1024
_MAX_TOTAL_BYTES = 32 * 1024 * 1024
_CANVAS = {"width": 320, "height": 400}
_HEX = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class VerifiedCharacterSprite:
    group: str
    variant: str
    z: int
    digest: str
    png: bytes


def _validated_manifest(root: Path) -> dict[tuple[str, str], dict]:
    raw = _read_file(root, PurePosixPath("manifest.json"), limit=_MAX_MANIFEST_BYTES)
    try:
        doc = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise Avatar2DAssetError("invalid public character art manifest") from exc
    if not isinstance(doc, dict) or doc.get("schema") != _SCHEMA:
        raise Avatar2DAssetError("unsupported character sprite manifest")
    if doc.get("canvas") != _CANVAS or doc.get("fixed_topology") != {
        "ears": 2, "tails": 1,
    }:
        raise Avatar2DAssetError("character rig canvas/topology mismatch")
    if doc.get("groups") != {
        name: list(variants) for name, variants in _PUBLIC_GROUPS.items()
    }:
        raise Avatar2DAssetError("character sprite variants mismatch")
    parts = doc.get("parts")
    expected = sum(map(len, _PUBLIC_GROUPS.values()))
    if not isinstance(parts, list) or len(parts) != expected:
        raise Avatar2DAssetError("incomplete public character art")
    entries: dict[tuple[str, str], dict] = {}
    seen_paths: set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            raise Avatar2DAssetError("invalid character sprite descriptor")
        group, variant = part.get("group"), part.get("variant")
        if not isinstance(group, str) or group not in _PUBLIC_GROUPS:
            raise Avatar2DAssetError("unknown character sprite group")
        if not isinstance(variant, str) or variant not in _PUBLIC_GROUPS[group]:
            raise Avatar2DAssetError("unknown character sprite variant")
        key = (group, variant)
        path = _relative_png(part.get("path"))
        digest = part.get("sha256")
        if (
            key in entries or str(path) in seen_paths
            or part.get("id") != f"{group}.{variant}"
            or part.get("anchor") != _ANCHOR[group]
            or part.get("z") != _Z[group]
            or part.get("audience") != "public"
            or not isinstance(digest, str)
            or not _HEX.fullmatch(digest)
        ):
            raise Avatar2DAssetError("unsafe or inconsistent character art descriptor")
        seen_paths.add(str(path))
        entries[key] = dict(part)
    if set(entries) != {
        (group, variant)
        for group, variants in _PUBLIC_GROUPS.items()
        for variant in variants
    }:
        raise Avatar2DAssetError("missing character sprites")
    return entries


def load_selected_character_sprites(
    root: Path, selection: CharacterPartSelection,
) -> tuple[VerifiedCharacterSprite, ...]:
    """Load only the selected 12 public parts, not all 33 into memory.

    The source-specific selection comes from canonical public appearance +
    existing expression decisions. No user-supplied asset path is accepted.
    """
    if not isinstance(root, Path) or not isinstance(selection, CharacterPartSelection):
        raise TypeError("public art root and validated character selection required")
    entries = _validated_manifest(root)
    chosen = selection.as_dict()
    if set(chosen) != set(_PUBLIC_GROUPS):
        raise Avatar2DAssetError("incomplete current character selection")
    output = []
    total_bytes = 0
    for group, variant in chosen.items():
        if not isinstance(variant, str) or (group, variant) not in entries:
            raise Avatar2DAssetError("character variant is not in approved art")
        entry = entries[(group, variant)]
        data = _read_file(
            root, _relative_png(entry["path"]), limit=_MAX_PNG_BYTES,
        )
        if sha256(data).hexdigest() != entry["sha256"]:
            raise Avatar2DAssetError("character art checksum mismatch")
        _verify_png(data)
        # The manifest's fixed canvas is authoritative for all image layers;
        # reject sprites with different PNG IHDR dimensions/format.
        if (
            int.from_bytes(data[16:20], "big") != _CANVAS["width"]
            or int.from_bytes(data[20:24], "big") != _CANVAS["height"]
        ):
            raise Avatar2DAssetError("character sprite canvas mismatch")
        total_bytes += len(data)
        if total_bytes > _MAX_TOTAL_BYTES:
            raise Avatar2DAssetError("character sprite memory limit exceeded")
        output.append(VerifiedCharacterSprite(
            group=group, variant=variant, z=_Z[group],
            digest=entry["sha256"], png=data,
        ))
    return tuple(sorted(output, key=lambda sprite: (sprite.z, sprite.group)))
