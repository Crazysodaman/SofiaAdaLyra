"""PKG-CORE foundation: truthful, grouped startup evidence.

Pure planning/formatting only. Not wired to the runtime or its SQLite store.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StartupEvidence:
    observed_at: datetime
    previous_runtime_observed: bool
    changed_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError('An aware observation time is required.')
        if not isinstance(self.previous_runtime_observed, bool):
            raise TypeError('Previous-runtime observation must be boolean.')
        if not isinstance(self.changed_paths, tuple) or any(
            not isinstance(path, str) or not path.strip() for path in self.changed_paths
        ):
            raise ValueError('Changed paths must be nonempty strings in a tuple.')

    def public_summary(self) -> str:
        """Summarize observed facts without revealing filenames or inferring causes."""
        runtime = ('A previous runtime was observed.' if self.previous_runtime_observed
                   else 'No previous runtime evidence was supplied.')
        count = len(set(self.changed_paths))
        changes = (f'{count} distinct workspace path(s) changed.' if count
                   else 'No workspace changes were supplied.')
        return f'{runtime} {changes}'
