"""Content-addressed AVATAR assets kept outside transactional state blobs."""

from __future__ import annotations

from dataclasses import dataclass
import re

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class AvatarAsset:
    asset_id: str
    sha256: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, str) or not self.asset_id.strip():
            raise ValueError("asset_id required")
        if not isinstance(self.sha256, str) or _DIGEST.fullmatch(self.sha256) is None:
            raise ValueError("sha256 must be lowercase SHA-256")
        if not isinstance(self.media_type, str) or not self.media_type.strip():
            raise ValueError("media_type required")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be nonnegative")
