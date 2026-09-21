"""PKG-CLEAN: pure cleanup review eligibility; deletes and moves nothing."""
from __future__ import annotations

from dataclasses import dataclass


_PROTECTED_ROOTS = frozenset({'.git', 'state', 'src/sofia/constitution',
                              'src/sofia/identity', 'src/sofia/data'})


def _protected(path: str) -> bool:
    return any(path == root or path.startswith(root + '/') for root in _PROTECTED_ROOTS)


@dataclass(frozen=True)
class CleanupCandidate:
    relative_paths: tuple[str, ...]
    backup_verified: bool = False
    owner_reviewed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.relative_paths, tuple) or not self.relative_paths:
            raise ValueError('At least one path is required.')
        for path in self.relative_paths:
            if not isinstance(path, str) or not path.strip():
                raise ValueError('Paths must be nonempty text.')
            normalized = path.replace('\\', '/')
            if (normalized.startswith('/') or ':' in normalized.split('/')[0]
                    or any(part in ('', '.', '..') for part in normalized.split('/'))):
                raise ValueError('Only normalized relative paths are permitted.')
        if not isinstance(self.backup_verified, bool) or not isinstance(self.owner_reviewed, bool):
            raise TypeError('Review flags must be boolean.')

    @property
    def eligible_for_manual_plan(self) -> bool:
        """Not deletion permission; protected paths require separate manual handling."""
        paths = tuple(path.replace('\\', '/') for path in self.relative_paths)
        return (self.backup_verified and self.owner_reviewed
                and not any(_protected(path) for path in paths))
