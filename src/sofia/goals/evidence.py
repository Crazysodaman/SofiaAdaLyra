"""Read-only lookup of durable host evidence identifiers used by goals."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3


class GoalEvidenceIndex:
    """Fail-closed whitelist over canonical evidence/receipt identifiers."""

    _SOURCES = (
        ("conversation_messages", "id"),
        ("interaction_evidence", "message_id"),
        ("interact_evidence_attestations", "source_id"),
        ("evolve_evidence", "evidence_id"),
        ("net_web_evidence", "evidence_id"),
        ("ops_maintenance_receipt", "receipt_id"),
        ("run_supervisor_events", "event_id"),
        ("state_plane_record", "source"),
    )

    def __init__(self, state_path: str | Path) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical state database is required")

    def __call__(self, evidence_ref: str) -> bool:
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            return False
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            db.execute("PRAGMA busy_timeout=5000")
            for table, column in self._SOURCES:
                exists = db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists is None:
                    continue
                columns = {
                    row[1] for row in db.execute(f"PRAGMA table_info({table})")
                }
                if column not in columns:
                    continue
                # Table and column are compile-time whitelist constants.
                row = db.execute(
                    f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1",
                    (evidence_ref,),
                ).fetchone()
                if row is not None:
                    return True
        return False
