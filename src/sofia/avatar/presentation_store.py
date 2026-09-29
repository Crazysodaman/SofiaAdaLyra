"""Durable JSON persistence for headless AVATAR presentation state."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sofia.state.atomic_file import atomic_write_text

from .presentation import PresentationAuthority, PresentationError
from .wardrobe import Wardrobe


class PresentationStoreError(RuntimeError):
    pass


class PresentationStore:
    """Atomically persist one settled PresentationAuthority snapshot."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def save(self, authority: PresentationAuthority) -> None:
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("PresentationStore requires PresentationAuthority")
        payload = authority.snapshot()
        try:
            atomic_write_text(
                self.path,
                json.dumps(
                    payload,
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
            )
        except OSError as exc:
            raise PresentationStoreError("failed to save presentation state") from exc

    def load(
        self,
        wardrobe: Wardrobe,
        *,
        outfits: dict[str, tuple[str, ...]],
    ) -> PresentationAuthority:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError as exc:
            raise PresentationStoreError("presentation state does not exist") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise PresentationStoreError("failed to load presentation state") from exc
        if not isinstance(raw, dict):
            raise PresentationStoreError("presentation state must be a JSON object")
        try:
            return PresentationAuthority.restore(
                wardrobe,
                outfits=outfits,
                snapshot=raw,
            )
        except (PresentationError, TypeError, ValueError) as exc:
            raise PresentationStoreError("presentation state is invalid") from exc

    def exists(self) -> bool:
        return self.path.is_file()
