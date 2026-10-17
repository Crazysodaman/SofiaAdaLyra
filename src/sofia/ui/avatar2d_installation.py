"""Conservative discovery of an owner-installed PUBLIC 2D sprite pack.

No generation, downloads, configuration writes, or protected/private wardrobe
discovery happens during desktop startup. An explicit configured path always
wins, including when its sprites are invalid: the renderer then safely falls
back instead of trying a different, unexpected pack.
"""
from __future__ import annotations

from pathlib import Path


_PUBLIC_DIRECTORY_NAMES = ("Public-V2", "Public-All", "Public")


def discover_public_avatar2d_root(
    configured_root: str | None, *, local_app_data: str | None
) -> Path | None:
    """Return an explicit root or a previously installed local public pack.

    Discovery only looks in known public installation directories in the
    current user's LOCALAPPDATA. A manifest presence check is deliberately
    cheap; the layered renderer performs authoritative manifest, PNG and hash
    verification before painting any layers.
    """
    if configured_root and configured_root.strip():
        return Path(configured_root.strip())

    if not local_app_data or not local_app_data.strip():
        return None

    base = Path(local_app_data) / "SofiaAdaLyra" / "Avatar2D"
    if base.is_symlink():
        return None
    for directory_name in _PUBLIC_DIRECTORY_NAMES:
        root = base / directory_name
        outfit = root / "outfits" / "day.default"
        character = root / "character"
        if any(
            path.is_symlink()
            for path in (
                root, root / "outfits", outfit, character,
                outfit / "manifest.json", character / "manifest.json",
            )
        ):
            continue
        if (
            (outfit / "manifest.json").is_file()
            and (character / "manifest.json").is_file()
        ):
            return root
    return None
