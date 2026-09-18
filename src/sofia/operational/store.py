from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.operational.model import (
    ContinuityEvidenceStatus,
    RuntimeContinuity,
)


class OperationalStore:
    """
    SQLite-backed persistence for runtime lifecycle evidence.

    Runtime history is operational evidence and is kept separate from
    Sofía's identity, memory, and cognitive state.

    A runtime is recorded only after successful startup. Therefore a
    failed startup cannot replace the previous successful runtime
    evidence.
    """

    def __init__(
        self,
        database_path: Path | str,
    ) -> None:
        self._database_path = Path(database_path)
        self._connection: sqlite3.Connection | None = None

        self.open()

    def open(self) -> None:
        if self._connection is not None:
            return

        self._connection = sqlite3.connect(
            str(self._database_path)
        )

        self._initialize_database()

    def _initialize_database(self) -> None:
        connection = self._require_connection()

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operational_runtime_history (
                runtime_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                stopped_at TEXT,
                lifecycle_state TEXT NOT NULL
            )
            """
        )

        connection.commit()

    def record_started(
        self,
        runtime_id: UUID,
        started_at: datetime,
    ) -> None:
        if not isinstance(runtime_id, UUID):
            raise TypeError(
                "OperationalStore runtime_id must be a UUID."
            )

        if not isinstance(started_at, datetime):
            raise TypeError(
                "OperationalStore started_at must be a datetime."
            )

        if started_at.tzinfo is None:
            raise ValueError(
                "OperationalStore started_at must be timezone-aware."
            )

        connection = self._require_connection()

        connection.execute(
            """
            INSERT INTO operational_runtime_history (
                runtime_id,
                started_at,
                stopped_at,
                lifecycle_state
            )
            VALUES (?, ?, NULL, ?)
            """,
            (
                str(runtime_id),
                started_at.isoformat(),
                "ready",
            ),
        )

        connection.commit()

    def record_stopped(
        self,
        runtime_id: UUID,
        stopped_at: datetime,
    ) -> None:
        if not isinstance(runtime_id, UUID):
            raise TypeError(
                "OperationalStore runtime_id must be a UUID."
            )

        if not isinstance(stopped_at, datetime):
            raise TypeError(
                "OperationalStore stopped_at must be a datetime."
            )

        if stopped_at.tzinfo is None:
            raise ValueError(
                "OperationalStore stopped_at must be timezone-aware."
            )

        connection = self._require_connection()

        connection.execute(
            """
            UPDATE operational_runtime_history
            SET stopped_at = ?,
                lifecycle_state = ?
            WHERE runtime_id = ?
            """,
            (
                stopped_at.isoformat(),
                "stopped",
                str(runtime_id),
            ),
        )

        connection.commit()

    def latest_runtime(
        self,
    ) -> tuple[
        UUID,
        datetime,
        datetime | None,
        str,
    ] | None:
        connection = self._require_connection()

        row = connection.execute(
            """
            SELECT
                runtime_id,
                started_at,
                stopped_at,
                lifecycle_state
            FROM operational_runtime_history
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()

        if row is None:
            return None

        return (
            UUID(row[0]),
            datetime.fromisoformat(row[1]),
            (
                datetime.fromisoformat(row[2])
                if row[2] is not None
                else None
            ),
            row[3],
        )

    def continuity_for(
        self,
        current_runtime_id: UUID,
        current_started_at: datetime,
    ) -> RuntimeContinuity:
        if not isinstance(current_runtime_id, UUID):
            raise TypeError(
                "OperationalStore current_runtime_id must be a UUID."
            )

        if not isinstance(current_started_at, datetime):
            raise TypeError(
                "OperationalStore current_started_at must be a datetime."
            )

        if current_started_at.tzinfo is None:
            raise ValueError(
                "OperationalStore current_started_at must be "
                "timezone-aware."
            )

        connection = self._require_connection()

        row = connection.execute(
            """
            SELECT
                runtime_id,
                started_at,
                stopped_at,
                lifecycle_state
            FROM operational_runtime_history
            WHERE runtime_id != ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (str(current_runtime_id),),
        ).fetchone()

        if row is None:
            return RuntimeContinuity(
                evidence_status=ContinuityEvidenceStatus.UNKNOWN,
                current_runtime_id=current_runtime_id,
                current_started_at=current_started_at,
            )

        return RuntimeContinuity(
            evidence_status=ContinuityEvidenceStatus.OBSERVED,
            current_runtime_id=current_runtime_id,
            current_started_at=current_started_at,
            previous_runtime_id=UUID(row[0]),
            previous_started_at=datetime.fromisoformat(row[1]),
            previous_stopped_at=(
                datetime.fromisoformat(row[2])
                if row[2] is not None
                else None
            ),
            previous_lifecycle_state=row[3],
        )

    def close(self) -> None:
        if self._connection is None:
            return

        self._connection.close()
        self._connection = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError(
                "OperationalStore must be opened before use."
            )

        return self._connection