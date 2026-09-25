"""Durable exact endpoint approvals for PKG-NET.

Persistence protects the reviewed destination boundary across restarts.
This still does not authenticate a peer, resolve DNS safely, or open sockets.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from uuid import UUID

from sofia.distributed.endpoint_policy import ApprovedEndpoint
from sofia.distributed.model import NodeEndpoint, NodeTransport


class DurableEndpointPolicy:
    def __init__(self, state_path: Path | str) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("an on-disk SQLite path is required")
        if str(state_path) == ":memory:":
            raise ValueError("in-memory storage is not durable")
        target = Path(state_path)
        if not target.parent.exists():
            raise FileNotFoundError("endpoint policy database parent must exist")
        self._db = sqlite3.connect(target, timeout=3.0)
        self._db.execute("PRAGMA busy_timeout = 3000")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS approved_remote_endpoint (
                node_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL,
                port INTEGER NOT NULL,
                transport TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0, 1))
            )
        """)
        self._db.commit()

    def approve(self, approval: ApprovedEndpoint) -> None:
        if not isinstance(approval, ApprovedEndpoint):
            raise TypeError("approval must be an ApprovedEndpoint")
        try:
            with self._db:
                self._db.execute(
                    """INSERT INTO approved_remote_endpoint
                       (node_id, hostname, port, transport, approved_by)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(approval.node_id), approval.endpoint.hostname,
                     approval.endpoint.port, approval.endpoint.transport.value,
                     approval.approved_by),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("node endpoint already recorded; revoke does not permit ID reuse") from exc

    def revoke(self, node_id: UUID) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        with self._db:
            self._db.execute(
                "UPDATE approved_remote_endpoint SET revoked = 1 WHERE node_id = ?",
                (str(node_id),),
            )

    def permits(self, node_id: UUID, endpoint: NodeEndpoint) -> bool:
        if not isinstance(node_id, UUID) or not isinstance(endpoint, NodeEndpoint):
            return False
        row = self._db.execute(
            """SELECT hostname, port, transport, revoked
               FROM approved_remote_endpoint WHERE node_id = ?""",
            (str(node_id),),
        ).fetchone()
        if row is None:
            return False
        hostname, port, transport, revoked = row
        return bool(
            revoked == 0
            and hostname == endpoint.hostname
            and port == endpoint.port
            and transport == endpoint.transport.value
        )

    def close(self) -> None:
        self._db.close()
