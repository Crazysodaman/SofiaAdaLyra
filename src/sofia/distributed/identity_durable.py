"""Durable node enrollment for PKG-NET.

Stores public-key fingerprints only. Rotation is intentionally not implicit:
a node must be explicitly retired before a replacement enrollment is created.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.distributed.identity import NodeEnrollment
from sofia.distributed.model import DistributedNode


class DurableNodeIdentityRegistry:
    def __init__(self, database_path: Path | str) -> None:
        if not isinstance(database_path, (str, Path)) or not str(database_path).strip():
            raise ValueError("an on-disk SQLite path is required")
        if str(database_path) == ":memory:":
            raise ValueError("in-memory enrollment is not durable")
        target = Path(database_path)
        if not target.parent.exists():
            raise FileNotFoundError("identity database parent directory must exist")
        self._db = sqlite3.connect(target, timeout=3.0)
        self._db.execute("PRAGMA busy_timeout = 3000")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS distributed_node_identity (
                node_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                public_key_sha256 TEXT NOT NULL UNIQUE,
                provisioned_at TEXT NOT NULL,
                recorded_by TEXT NOT NULL,
                retired INTEGER NOT NULL DEFAULT 0 CHECK (retired IN (0,1))
            )
        """)
        self._db.commit()

    def enroll(self, enrollment: NodeEnrollment) -> None:
        if not isinstance(enrollment, NodeEnrollment):
            raise TypeError("enrollment must be a NodeEnrollment")
        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO distributed_node_identity
                       (node_id, name, public_key_sha256, provisioned_at, recorded_by)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(enrollment.node.node_id), enrollment.node.name,
                     enrollment.public_key_sha256,
                     enrollment.provisioned_at.isoformat(), enrollment.recorded_by),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("node ID or public-key pin is already recorded") from exc

    def get(self, node_id: UUID) -> NodeEnrollment | None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        row = self._db.execute(
            """SELECT name, public_key_sha256, provisioned_at, recorded_by, retired
               FROM distributed_node_identity WHERE node_id = ?""",
            (str(node_id),),
        ).fetchone()
        if row is None or row[4]:
            return None
        return NodeEnrollment(
            DistributedNode(node_id, row[0]), row[1],
            datetime.fromisoformat(row[2]), row[3],
        )

    def active(self) -> tuple[NodeEnrollment, ...]:
        rows = self._db.execute(
            """SELECT node_id, name, public_key_sha256, provisioned_at, recorded_by
               FROM distributed_node_identity WHERE retired = 0 ORDER BY name, node_id"""
        ).fetchall()
        return tuple(
            NodeEnrollment(
                DistributedNode(UUID(row[0]), row[1]),
                row[2],
                datetime.fromisoformat(row[3]),
                row[4],
            )
            for row in rows
        )

    def retire(self, node_id: UUID) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        with self._db:
            self._db.execute(
                "UPDATE distributed_node_identity SET retired = 1 WHERE node_id = ?",
                (str(node_id),),
            )

    def close(self) -> None:
        self._db.close()
