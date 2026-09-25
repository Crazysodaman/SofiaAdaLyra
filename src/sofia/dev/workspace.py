"""Filesystem scope guard for bounded engineering work."""
from __future__ import annotations
from pathlib import Path

class WorkspaceViolation(RuntimeError): pass

class WorkspaceGuard:
    def __init__(self, root: Path, allowed_paths: tuple[str, ...]) -> None:
        self.root=root.resolve()
        self.allowed=frozenset(allowed_paths)
        if not self.root.is_dir(): raise ValueError("workspace root must exist")
        if not self.allowed: raise ValueError("allowed_paths required")

    def resolve_allowed(self, relative_path: str) -> Path:
        if relative_path not in self.allowed: raise WorkspaceViolation(f"path outside approved change scope: {relative_path}")
        candidate=(self.root / relative_path).resolve(strict=False)
        try: candidate.relative_to(self.root)
        except ValueError as exc: raise WorkspaceViolation("path escapes workspace") from exc
        # Existing symlinks/reparse-like links are never accepted as write targets.
        current=self.root
        for part in Path(relative_path).parts:
            current=current / part
            if current.exists() and current.is_symlink(): raise WorkspaceViolation(f"symlink write target denied: {relative_path}")
        return candidate
