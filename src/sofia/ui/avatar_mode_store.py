"""One durable *desktop preference* in existing canonical sofia.db.

Avatar geometry, clothing, emotions and memory are NOT duplicated here.
The setting never authenticates a private audience or marks a 3D rig ready.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path

from sofia.state.canonical_sqlite import CanonicalSQLiteGuard
from .avatar_mode import AvatarVisualMode


class AvatarModePreferenceStore:
    _KEY = "active-avatar-visual-mode"

    def __init__(self, state_path: Path | str) -> None:
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS ui_avatar_visual_preferences ("
                "setting_key TEXT PRIMARY KEY, visual_mode TEXT NOT NULL)"
            )

    def load(self) -> AvatarVisualMode:
        with closing(self._guard.connect(timeout=10)) as db:
            row = db.execute(
                "SELECT visual_mode FROM ui_avatar_visual_preferences WHERE setting_key=?",
                (self._KEY,),
            ).fetchone()
        if row is None:
            return AvatarVisualMode.TWO_D
        return AvatarVisualMode(str(row[0]))

    def save(self, mode: AvatarVisualMode) -> None:
        if not isinstance(mode, AvatarVisualMode):
            raise ValueError("invalid visual mode")
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute(
                "INSERT INTO ui_avatar_visual_preferences(setting_key,visual_mode) "
                "VALUES (?,?) ON CONFLICT(setting_key) DO UPDATE SET "
                "visual_mode=excluded.visual_mode",
                (self._KEY, mode.value),
            )
