"""Shared filesystem-boundary classification for protected local artifacts."""
from __future__ import annotations

from pathlib import Path


def inside_git_worktree(path: Path | str) -> bool:
    """Return whether *path* is contained by recognizable Git metadata.

    A linked worktree uses a ``.git`` indirection file. A normal checkout has
    a metadata directory containing ``HEAD`` plus object or common metadata.
    Empty sentinel directories mounted at broad container roots are not Git
    worktrees and must not make all independent local paths unusable.
    """
    candidate = Path(path)
    base = candidate if candidate.is_dir() else candidate.parent
    for parent in (base, *base.parents):
        marker = parent / ".git"
        try:
            if marker.is_file():
                return True
            if (
                marker.is_dir()
                and (marker / "HEAD").is_file()
                and (
                    (marker / "objects").is_dir()
                    or (marker / "commondir").is_file()
                )
            ):
                return True
        except OSError:
            # An unreadable candidate control path cannot safely be dismissed.
            return True
    return False
