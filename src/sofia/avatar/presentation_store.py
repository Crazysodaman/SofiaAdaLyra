"""Durable SQLite persistence for headless AVATAR presentation state."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .presentation import (
    AppearanceState,
    PresentationAuthority,
    PresentationDenied,
    PresentationError,
)
from .wardrobe import Wardrobe


class PresentationStoreError(RuntimeError):
    pass


class PresentationStore:
    """Persist one settled PresentationAuthority in canonical sofia.db."""

    _KEY = "canonical"
    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS avatar_presentation_state (
            state_key TEXT PRIMARY KEY,
            snapshot_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """

    _HISTORY_SCHEMA = """
        CREATE TABLE IF NOT EXISTS avatar_appearance_history (
            revision INTEGER PRIMARY KEY,
            appearance_json TEXT NOT NULL,
            outfit_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )
    """
    _FAVORITES_SCHEMA = """
        CREATE TABLE IF NOT EXISTS avatar_style_favorites (
            name TEXT PRIMARY KEY,
            appearance_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                db.execute("PRAGMA busy_timeout = 10000")
                db.execute(self._SCHEMA)
                db.execute(self._HISTORY_SCHEMA)
                db.execute(self._FAVORITES_SCHEMA)
                db.commit()
        except sqlite3.Error as exc:
            raise PresentationStoreError(
                "failed to initialize presentation state"
            ) from exc

    @property
    def database_path(self) -> Path:
        return self.path

    def save(self, authority: PresentationAuthority) -> None:
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("PresentationStore requires PresentationAuthority")
        payload = authority.snapshot()
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                db.execute("PRAGMA busy_timeout = 10000")
                previous_row = db.execute(
                    "SELECT snapshot_json FROM avatar_presentation_state WHERE state_key=?",
                    (self._KEY,),
                ).fetchone()
                db.execute(
                    """
                    INSERT INTO avatar_presentation_state (
                        state_key,
                        snapshot_json,
                        updated_at
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(state_key) DO UPDATE SET
                        snapshot_json=excluded.snapshot_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        self._KEY,
                        encoded,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                current = payload["current"]
                if previous_row is not None:
                    old = json.loads(previous_row[0])
                    previous_current = old["current"]
                    # Only record settled public appearances; never archive
                    # private outfit identifiers or private presentation state.
                    if (
                        current["revision"] > previous_current["revision"]
                        and not current["private_only"]
                        and current["attire"] == "clothed"
                        and (
                            current["appearance"] != previous_current["appearance"]
                            or current["outfit_id"] != previous_current["outfit_id"]
                        )
                    ):
                        db.execute(
                            """
                            INSERT OR IGNORE INTO avatar_appearance_history
                                (revision, appearance_json, outfit_id, reason, occurred_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                current["revision"],
                                json.dumps(current["appearance"], sort_keys=True),
                                current["outfit_id"],
                                current["reason"],
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                    # Compensating rollback can restore an earlier revision;
                    # discard entries associated with rejected transitions.
                    elif current["revision"] < previous_current["revision"]:
                        db.execute(
                            "DELETE FROM avatar_appearance_history WHERE revision > ?",
                            (current["revision"],),
                        )
                db.commit()
        except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            raise PresentationStoreError(
                "failed to save presentation state"
            ) from exc

    def recent_appearance_history(self, *, limit: int = 25) -> tuple[dict, ...]:
        """Return recorded public looks, newest first, never private changes."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("history limit must be 1..100")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                """
                SELECT revision, appearance_json, outfit_id, reason, occurred_at
                FROM avatar_appearance_history ORDER BY revision DESC LIMIT ?
                """, (limit,),
            ).fetchall()
        return tuple({
            "revision": revision, "appearance": json.loads(appearance),
            "outfit_id": outfit, "reason": reason, "occurred_at": time,
        } for revision, appearance, outfit, reason, time in rows)

    def save_style_favorite(self, *, name: str, appearance: AppearanceState) -> None:
        """Store a reversible visual preset, not physical anatomy or grant state."""
        if not isinstance(name, str) or not name.strip() or len(name) > 60:
            raise ValueError("invalid favorite name")
        if not isinstance(appearance, AppearanceState):
            raise TypeError("favorite appearance must be AppearanceState")
        # Reuse authority's public, strictly validated appearance serialization.
        values = {
            "hairstyle": appearance.hairstyle, "hair_color": appearance.hair_color,
            "tail_color": appearance.tail_color, "style_tags": list(appearance.style_tags),
            "hair_length": appearance.hair_length, "hair_design": appearance.hair_design,
            "eye_color": appearance.eye_color, "posture": appearance.posture,
            "ear_pose": appearance.ear_pose, "tail_pose": appearance.tail_pose,
            "expression": appearance.expression, "fur_style": appearance.fur_style,
            "makeup": appearance.makeup, "freckles": appearance.freckles,
            "tattoos": list(appearance.tattoos), "piercings": list(appearance.piercings),
        }
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            db.execute(
                """
                INSERT INTO avatar_style_favorites(name, appearance_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                appearance_json=excluded.appearance_json, updated_at=excluded.updated_at
                """,
                (name.strip(), json.dumps(values, sort_keys=True),
                 datetime.now(timezone.utc).isoformat()),
            )

    def list_style_favorites(self) -> dict[str, AppearanceState]:
        """Return saved looks without mutating canonical presentation."""
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db:
            rows = db.execute(
                "SELECT name, appearance_json FROM avatar_style_favorites ORDER BY name"
            ).fetchall()
        return {
            name: PresentationAuthority._appearance_from_dict(json.loads(raw))
            for name, raw in rows
        }

    def delete_style_favorite(self, name: str) -> bool:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("invalid favorite name")
        with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
            result = db.execute(
                "DELETE FROM avatar_style_favorites WHERE name=?", (name.strip(),)
            )
            return result.rowcount > 0

    def persist_mutation(
        self,
        authority: PresentationAuthority,
        mutation: Callable[[], object],
    ) -> object:
        """Commit one authority mutation and durable snapshot as one host unit.

        SQLite owns the durable commit. If mutation or persistence fails, the
        live authority is restored to its exact settled checkpoint. If the
        write succeeded but verification failed, make one best-effort
        compensating save of the checkpoint before re-raising.
        """
        if not isinstance(authority, PresentationAuthority):
            raise TypeError("authority must be PresentationAuthority")
        if not callable(mutation):
            raise TypeError("mutation must be callable")

        checkpoint = authority.snapshot()
        saved = False
        try:
            result = mutation()
            self.save(authority)
            saved = True
            stored = self._read_snapshot_json()
            if stored is None:
                raise PresentationStoreError(
                    "presentation mutation was not durably recorded"
                )
            try:
                persisted = json.loads(stored)
            except (TypeError, json.JSONDecodeError) as exc:
                raise PresentationStoreError(
                    "presentation mutation verification could not decode state"
                ) from exc
            if persisted != authority.snapshot():
                raise PresentationStoreError(
                    "presentation mutation verification did not match live state"
                )
            return result
        except Exception as exc:
            authority.restore_snapshot(checkpoint)
            if saved:
                try:
                    self.save(authority)
                except Exception as rollback_exc:
                    try:
                        exc.add_note(
                            "Presentation rollback restored memory but the "
                            "compensating durable save also failed: "
                            + type(rollback_exc).__name__
                        )
                    except AttributeError:
                        pass
            raise

    def load(
        self,
        wardrobe: Wardrobe,
        *,
        outfits: dict[str, tuple[str, ...]],
    ) -> PresentationAuthority:
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                row = db.execute(
                    """
                    SELECT snapshot_json
                    FROM avatar_presentation_state
                    WHERE state_key=?
                    """,
                    (self._KEY,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise PresentationStoreError(
                "failed to load presentation state"
            ) from exc
        if row is None:
            raise PresentationStoreError(
                "presentation state does not exist"
            )
        try:
            raw = json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as exc:
            raise PresentationStoreError(
                "failed to decode presentation state"
            ) from exc
        if not isinstance(raw, dict):
            raise PresentationStoreError(
                "presentation state must be a JSON object"
            )
        try:
            return PresentationAuthority.restore(
                wardrobe,
                outfits=outfits,
                snapshot=raw,
            )
        except (
            PresentationDenied,
            PresentationError,
            TypeError,
            ValueError,
        ) as exc:
            raise PresentationStoreError(
                "presentation state is invalid"
            ) from exc

    def _read_snapshot_json(self) -> str | None:
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                row = db.execute(
                    """
                    SELECT snapshot_json
                    FROM avatar_presentation_state
                    WHERE state_key=?
                    """,
                    (self._KEY,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise PresentationStoreError(
                "failed to inspect presentation state"
            ) from exc
        return None if row is None else row[0]

    def exists(self) -> bool:
        return self._read_snapshot_json() is not None
