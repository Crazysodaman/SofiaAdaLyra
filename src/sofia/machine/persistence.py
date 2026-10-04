"""Canonical SQLite machine inventory and legacy JSON import."""
import json
from contextlib import closing
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sofia.state.atomic_file import retire_legacy_file

from sofia.machine.inventory import MachineInventory
from sofia.machine.inventory_codec import deserialize_inventory, serialize_inventory


def load_legacy_inventory(path: Path) -> MachineInventory:
    """Read an existing legacy snapshot for one-time import."""
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Machine inventory file does not exist: "
            f"{path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Machine inventory file contains invalid "
            f"JSON: {path}"
        ) from exc

    return deserialize_inventory(payload)




class SQLiteMachineInventoryPersistence:
    """Canonical SQLite persistence for MACHINE inventory state."""

    _KEY = "canonical"

    def __init__(
        self,
        path: str | Path,
        *,
        legacy_path: str | Path | None = None,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS machine_inventory_state (
                    state_key TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.commit()
        if legacy_path is not None:
            self._migrate_legacy(Path(legacy_path))

    @property
    def path(self) -> Path:
        return self._path

    def save(self, inventory: MachineInventory) -> None:
        payload = serialize_inventory(inventory)
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        with closing(sqlite3.connect(self._path, timeout=10.0)) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                INSERT INTO machine_inventory_state(
                    state_key,snapshot_json,updated_at
                )
                VALUES(?,?,?)
                ON CONFLICT(state_key) DO UPDATE SET
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
            """,(
                self._KEY,
                encoded,
                datetime.now(timezone.utc).isoformat(),
            ))
            db.commit()

    def load(self) -> MachineInventory:
        with closing(sqlite3.connect(self._path, timeout=10.0)) as db, db:
            row = db.execute("""
                SELECT snapshot_json
                FROM machine_inventory_state
                WHERE state_key=?
            """,(self._KEY,)).fetchone()
        if row is None:
            raise FileNotFoundError(
                "Machine inventory does not exist in canonical state database: "
                f"{self._path}"
            )
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Machine inventory state contains invalid JSON."
            ) from exc
        return deserialize_inventory(payload)

    def _migrate_legacy(self, legacy_path: Path) -> None:
        if not legacy_path.is_file():
            return
        legacy = load_legacy_inventory(legacy_path)
        try:
            current = self.load()
        except FileNotFoundError:
            self.save(legacy)
            current = self.load()
        if serialize_inventory(current) != serialize_inventory(legacy):
            raise RuntimeError(
                "legacy machine-inventory.json conflicts with canonical sofia.db"
            )
        retire_legacy_file(legacy_path)
