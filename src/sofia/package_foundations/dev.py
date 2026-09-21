"""PKG-DEV: inspectable change proposal; no filesystem, shell or Git execution."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ChangeProposal:
    relative_path: str
    expected_sha256: str
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.relative_path, str):
            raise TypeError('Path must be text.')
        path = self.relative_path.replace('\\', '/')
        parts = path.split('/')
        if (not path or path.startswith('/') or ':' in parts[0]
                or any(part in ('', '.', '..') for part in parts)):
            raise ValueError('Only normalized in-repository relative paths are permitted.')
        if not isinstance(self.expected_sha256, str) or not re.fullmatch(
            r'[a-fA-F0-9]{64}', self.expected_sha256
        ):
            raise ValueError('A pinned 64-hex-character SHA-256 is required.')
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError('A nonempty rationale is required.')

    @property
    def normalized_path(self) -> str:
        return self.relative_path.replace('\\', '/')
