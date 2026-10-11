"""Authenticated per-device read cursors for canonical lifelong Main.

Read acknowledgements are never message delivery or cross-audience grants.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from sofia.social.model import PrincipalContext
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


class MobileMainSeenStore:
    """Stores read progress in sofia.db, scoped by device, mode and credential epoch."""

    def __init__(self, state_path: Path | str) -> None:
        self._guard = CanonicalSQLiteGuard(state_path)
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS mobile_main_seen (
                    device_id TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('private','standard')),
                    credential_generation INTEGER NOT NULL CHECK(credential_generation>=1),
                    canonical_sequence INTEGER NOT NULL CHECK(canonical_sequence>=1),
                    turn_position INTEGER NOT NULL CHECK(turn_position IN (0,1)),
                    message_id TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    PRIMARY KEY(device_id,mode,credential_generation)
                )
            """)

    @staticmethod
    def _scope(device_id: str, private_mode: bool, generation: int):
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device ID required")
        if type(private_mode) is not bool:
            raise TypeError("private_mode must be bool")
        if type(generation) is not int or generation < 1:
            raise PermissionError("active device credential generation required")
        return (device_id, "private" if private_mode else "standard", generation)

    def current(
        self, *, device_id: str, private_mode: bool, generation: int,
        principal: PrincipalContext,
    ) -> dict[str, object] | None:
        """Expose a read marker only while its original is still visible.

        The receipt remains durably recorded for reconciliation, but a
        revoked/rebound/deleted source cannot be used as a cursor hint to a
        phone that no longer has rights to its originating conversation.
        """
        scope = self._scope(device_id, private_mode, generation)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        with closing(self._guard.connect(timeout=10)) as db:
            row = db.execute(
                "SELECT seen.canonical_sequence,seen.turn_position,"
                "seen.message_id FROM mobile_main_seen AS seen "
                "JOIN lifelong_thread_event AS e "
                "ON e.canonical_sequence=seen.canonical_sequence "
                "AND e.turn_position=seen.turn_position "
                "AND e.source_message_id=seen.message_id "
                "JOIN lifelong_thread AS t ON t.thread_id=e.thread_id "
                "JOIN conversation_messages AS m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal AS s ON s.session_id=m.session_id "
                "WHERE seen.device_id=? AND seen.mode=? "
                "AND seen.credential_generation=? "
                "AND t.kind='main' AND t.owner_principal_id=? "
                "AND e.source_audience_id=? AND e.visibility='source_audience' "
                "AND s.principal_id=? AND s.audience_id=? AND s.audience_kind=? "
                "LIMIT 1",
                (
                    *scope, principal.principal_id, principal.audience_id,
                    principal.principal_id, principal.audience_id,
                    principal.audience_kind.value,
                ),
            ).fetchone()
        return self._cursor(row)

    @staticmethod
    def _cursor(row) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "canonical_sequence": int(row[0]),
            "turn_position": int(row[1]),
            "message_id": str(row[2]),
        }

    def acknowledge(
        self, *, device_id: str, private_mode: bool, generation: int,
        principal: PrincipalContext, canonical_sequence: int,
        turn_position: int, message_id: str, credential_sha256: str,
    ) -> dict[str, object]:
        scope = self._scope(device_id, private_mode, generation)
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated principal required")
        if (
            not isinstance(credential_sha256, str)
            or len(credential_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in credential_sha256)
        ):
            raise PermissionError("verified device bearer digest required")
        if type(canonical_sequence) is not int or canonical_sequence < 1:
            raise ValueError("positive canonical sequence required")
        if type(turn_position) is not int or turn_position not in (0, 1):
            raise ValueError("turn position must be 0 or 1")
        if not isinstance(message_id, str) or not 1 <= len(message_id) <= 160:
            raise ValueError("bounded source message ID required")
        with closing(self._guard.connect(timeout=10)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            # The same SQLite writer transaction serializes credential
            # rotation/revocation with read acknowledgment. Authentication
            # performed before queued dispatch is not enough.
            current = db.execute(
                "SELECT 1 FROM mobile_device_credential "
                "WHERE device_id=? AND generation=? "
                "AND token_sha256=? AND status='active' LIMIT 1",
                (device_id, generation, credential_sha256),
            ).fetchone()
            if current is None:
                raise PermissionError("pairing changed before Main receipt commit")
            row = db.execute(
                "SELECT 1 FROM lifelong_thread_event e "
                "JOIN lifelong_thread t ON t.thread_id=e.thread_id "
                "JOIN conversation_messages m "
                "ON m.id=e.source_message_id AND m.session_id=e.source_session_id "
                "JOIN social_session_principal s ON s.session_id=m.session_id "
                "WHERE t.kind='main' AND t.owner_principal_id=? "
                "AND e.source_audience_id=? AND e.visibility='source_audience' "
                "AND s.principal_id=? AND s.audience_id=? AND s.audience_kind=? "
                "AND e.canonical_sequence=? AND e.turn_position=? "
                "AND e.source_message_id=? LIMIT 1",
                (
                    principal.principal_id, principal.audience_id,
                    principal.principal_id, principal.audience_id,
                    principal.audience_kind.value,
                    canonical_sequence, turn_position, message_id,
                ),
            ).fetchone()
            if row is None:
                raise PermissionError("read cursor does not belong to this audience")
            db.execute(
                "INSERT INTO mobile_main_seen "
                "(device_id,mode,credential_generation,canonical_sequence,"
                "turn_position,message_id,seen_at) VALUES(?,?,?,?,?,?,?) "
                "ON CONFLICT(device_id,mode,credential_generation) DO UPDATE SET "
                "canonical_sequence=excluded.canonical_sequence,"
                "turn_position=excluded.turn_position,"
                "message_id=excluded.message_id,seen_at=excluded.seen_at "
                "WHERE excluded.canonical_sequence>mobile_main_seen.canonical_sequence "
                "OR (excluded.canonical_sequence=mobile_main_seen.canonical_sequence "
                "AND excluded.turn_position>mobile_main_seen.turn_position)",
                (
                    *scope, canonical_sequence, turn_position, message_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            saved = db.execute(
                "SELECT canonical_sequence,turn_position,message_id "
                "FROM mobile_main_seen WHERE device_id=? AND mode=? "
                "AND credential_generation=?", scope,
            ).fetchone()
        return {"acknowledged": True, "last_seen": self._cursor(saved)}
