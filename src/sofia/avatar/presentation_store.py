"""Durable SQLite persistence for headless AVATAR presentation state."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .presentation import (
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

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(sqlite3.connect(self.path, timeout=10.0)) as db, db:
                db.execute("PRAGMA busy_timeout = 10000")
                db.execute(self._SCHEMA)
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
                db.commit()
        except sqlite3.Error as exc:
            raise PresentationStoreError(
                "failed to save presentation state"
            ) from exc

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
            stored = self.snapshot_json()
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

    def exists(self) -> bool:
        return self.snapshot_json() is not None
