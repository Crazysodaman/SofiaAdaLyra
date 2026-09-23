"""Durable virtual location, distinct from the synthetic InteractionLab harness.

This is a local world-state kernel, NOT physical equipment control, a renderer,
trusted chat parsing, or an authorization boundary. An application/controller
must authenticate actors and authorize requests before calling perform().
Only committed transitions are reported as completed world actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")
_ACTIONS = frozenset({"enter", "leave", "pick_up", "put_down", "work_on", "finish_work"})


def _id(value: str, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} requires a bounded ASCII identifier.")
    return value


def _utc(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("World action requires an aware timestamp.")
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorldAction:
    request_id: str
    actor_id: str
    verb: str
    target_id: str
    evidence_ref: str
    occurred_at: datetime
    tool_id: str | None = None

    def __post_init__(self) -> None:
        for label in ("request_id", "actor_id", "target_id", "evidence_ref"):
            _id(getattr(self, label), label)
        if self.verb not in _ACTIONS:
            raise ValueError("Unsupported virtual world action.")
        if self.tool_id is not None:
            _id(self.tool_id, "tool_id")
        if (self.verb == "work_on") != (self.tool_id is not None):
            raise ValueError("Only work_on requires a specific held tool.")
        _utc(self.occurred_at)

    def payload(self) -> str:
        return json.dumps({"actor_id": self.actor_id, "verb": self.verb,
                           "target_id": self.target_id, "tool_id": self.tool_id,
                           "evidence_ref": self.evidence_ref,
                           "occurred_at": _utc(self.occurred_at)}, sort_keys=True)


@dataclass(frozen=True)
class WorldOutcome:
    request_id: str
    status: str  # completed or denied
    reason: str
    actor_id: str
    verb: str
    target_id: str


class LabWorld:
    """Authoritative on-disk virtual room, actor and object state.

    Setup is an explicit trusted authoring operation, never an LLM side effect.
    SQL transactions and unique request IDs make replay idempotent across boots.
    """

    def __init__(self, state_path: str | Path) -> None:
        if not isinstance(state_path, (str, Path)) or not str(state_path).strip():
            raise ValueError("A persistent lab SQLite path is required.")
        self.path = Path(state_path)
        if str(state_path) == ":memory:" or not self.path.parent.is_dir():
            raise ValueError("Lab state must use an existing on-disk directory.")
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS lab_rooms (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_actors (
                    id TEXT PRIMARY KEY, room_id TEXT REFERENCES lab_rooms(id)
                );
                CREATE TABLE IF NOT EXISTS lab_objects (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('tool', 'equipment')),
                    room_id TEXT NOT NULL REFERENCES lab_rooms(id),
                    held_by TEXT REFERENCES lab_actors(id),
                    state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_action_log (
                    request_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    status TEXT NOT NULL, reason TEXT NOT NULL,
                    actor_id TEXT NOT NULL, verb TEXT NOT NULL,
                    target_id TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    def add_room(self, room_id: str, name: str) -> None:
        _id(room_id, "room_id")
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 100:
            raise ValueError("A room name is required.")
        with self._connect() as db:
            db.execute("INSERT INTO lab_rooms VALUES (?, ?)", (room_id, name.strip()))

    def add_actor(self, actor_id: str) -> None:
        _id(actor_id, "actor_id")
        with self._connect() as db:
            db.execute("INSERT INTO lab_actors VALUES (?, NULL)", (actor_id,))

    def add_object(self, object_id: str, name: str, kind: str, room_id: str) -> None:
        _id(object_id, "object_id")
        _id(room_id, "room_id")
        if kind not in ("tool", "equipment") or not isinstance(name, str) or not 0 < len(name.strip()) <= 100:
            raise ValueError("A named tool or equipment item is required.")
        state = "available" if kind == "tool" else "idle"
        with self._connect() as db:
            db.execute("INSERT INTO lab_objects VALUES (?, ?, ?, ?, NULL, ?)",
                       (object_id, name.strip(), kind, room_id, state))

    def snapshot(self) -> dict[str, tuple[tuple[object, ...], ...]]:
        """Read actual persisted location and inventory; no imagined objects."""
        with self._connect() as db:
            rooms = tuple(db.execute("SELECT id, name FROM lab_rooms ORDER BY id"))
            actors = tuple(db.execute("SELECT id, room_id FROM lab_actors ORDER BY id"))
            objects = tuple(db.execute(
                "SELECT id, name, kind, room_id, held_by, state FROM lab_objects ORDER BY id"))
        return {"rooms": rooms, "actors": actors, "objects": objects}

    def perform(self, action: WorldAction) -> WorldOutcome:
        """Run one trusted/authorized virtual-world action exactly once.

        Denied attempts are audited and replay as denied. A reused ID with
        different parameters fails visibly instead of silently doing new work.
        """
        if not isinstance(action, WorldAction):
            raise TypeError("WorldAction is required.")
        payload = action.payload()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT payload, status, reason, actor_id, verb, target_id "
                "FROM lab_action_log WHERE request_id = ?", (action.request_id,)
            ).fetchone()
            if prior is not None:
                if prior[0] != payload:
                    raise ValueError("A world request ID cannot be reused for another action.")
                return WorldOutcome(action.request_id, *prior[1:])
            status, reason = self._transition(db, action)
            db.execute("INSERT INTO lab_action_log VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (action.request_id, payload, status, reason, action.actor_id,
                        action.verb, action.target_id))
            return WorldOutcome(action.request_id, status, reason,
                                action.actor_id, action.verb, action.target_id)

    @staticmethod
    def _transition(db: sqlite3.Connection, a: WorldAction) -> tuple[str, str]:
        actor = db.execute("SELECT room_id FROM lab_actors WHERE id=?", (a.actor_id,)).fetchone()
        if actor is None:
            return "denied", "Actor has not been enrolled in the virtual world."
        room = actor[0]
        if a.verb == "enter":
            if db.execute("SELECT 1 FROM lab_rooms WHERE id=?", (a.target_id,)).fetchone() is None:
                return "denied", "That virtual room does not exist."
            if room == a.target_id:
                return "denied", "Actor is already in that room."
            db.execute("UPDATE lab_actors SET room_id=? WHERE id=?", (a.target_id, a.actor_id))
            return "completed", "Actor entered the virtual room."
        if a.verb == "leave":
            if room is None or room != a.target_id:
                return "denied", "Actor is not in that room."
            if db.execute("SELECT 1 FROM lab_objects WHERE held_by=?", (a.actor_id,)).fetchone():
                return "denied", "Put down held tools before leaving."
            db.execute("UPDATE lab_actors SET room_id=NULL WHERE id=?", (a.actor_id,))
            return "completed", "Actor left the virtual room."
        if room is None:
            return "denied", "Actor must enter a room first."
        item = db.execute(
            "SELECT kind, room_id, held_by, state FROM lab_objects WHERE id=?",
            (a.target_id,),
        ).fetchone()
        if item is None:
            return "denied", "The object does not exist."
        kind, item_room, held_by, state = item
        if item_room != room:
            return "denied", "Object is not in the actor's room."
        if a.verb == "pick_up":
            if kind != "tool" or held_by is not None:
                return "denied", "Target is not an available tool."
            db.execute("UPDATE lab_objects SET held_by=?, state='held' WHERE id=?",
                       (a.actor_id, a.target_id))
            return "completed", "Actor picked up the virtual tool."
        if a.verb == "put_down":
            if kind != "tool" or held_by != a.actor_id:
                return "denied", "Actor does not hold this tool."
            db.execute("UPDATE lab_objects SET held_by=NULL, state='available' WHERE id=?",
                       (a.target_id,))
            return "completed", "Actor put down the virtual tool."
        if kind != "equipment" or held_by is not None:
            return "denied", "Target is not available virtual equipment."
        if a.verb == "work_on":
            tool = db.execute("SELECT kind, room_id, held_by FROM lab_objects WHERE id=?",
                              (a.tool_id,)).fetchone()
            if tool != ("tool", room, a.actor_id):
                return "denied", "Actor must hold the specified tool in this room."
            if state != "idle":
                return "denied", "Equipment is not idle."
            db.execute("UPDATE lab_objects SET state='work_in_progress' WHERE id=?", (a.target_id,))
            return "completed", "Virtual equipment work started; no repair is claimed."
        if a.verb == "finish_work":
            if state != "work_in_progress":
                return "denied", "No work session is in progress."
            db.execute("UPDATE lab_objects SET state='work_finished' WHERE id=?", (a.target_id,))
            return "completed", "Virtual work session finished; equipment function is unverified."
        raise AssertionError("Unexpected validated action verb.")
