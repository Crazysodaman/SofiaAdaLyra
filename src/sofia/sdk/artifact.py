"""Shared immutable artifact references; no installation or execution authority."""
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
import re
import unicodedata

MAX_ARTIFACT_BYTES = 512 * 1024 * 1024


def validate_artifact_path(path: str) -> None:
    if not isinstance(path, str) or not 1 <= len(path.encode('utf-8')) <= 1024:
        raise ValueError('bounded artifact path required')
    parts = path.split('/')
    if (PurePosixPath(path).is_absolute() or any(p in {'', '.', '..'} for p in parts)
            or any(c in path for c in ('\\', ':'))
            or any(unicodedata.category(c).startswith('C') for c in path)):
        raise ValueError('artifact path must be unambiguous and package-relative')
    if any(p.endswith((' ', '.')) or PureWindowsPath(p).is_reserved() for p in parts):
        raise ValueError('ambiguous or reserved Windows artifact path')


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self):
        validate_artifact_path(self.path)
        if not isinstance(self.sha256, str) or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ValueError('lowercase SHA-256 required')
        if type(self.size_bytes) is not int or not 1 <= self.size_bytes <= MAX_ARTIFACT_BYTES:
            raise ValueError('artifact size must be within 1..512 MiB')

    def to_payload(self):
        return dict(path=self.path, sha256=self.sha256, size_bytes=self.size_bytes)

    @classmethod
    def from_payload(cls, value):
        if type(value) is not dict or set(value) != {'path','sha256','size_bytes'}:
            raise ValueError('artifact reference fields differ')
        return cls(**value)
