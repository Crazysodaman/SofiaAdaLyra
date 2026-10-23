"""Canonical SQLite metadata store for Sofía's scalable virtual world."""
from __future__ import annotations

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .world_model import (
    ObjectKind, ScenePage, SpaceKind, Transform, WorldMutationReceipt,
    WorldObject, WorldSpace, aware, bounded_text, world_id,
)


class VirtualWorldStore:
    """One canonical metadata owner; assets remain external and hash-addressed."""

    def __init__(
        self, state_path: Path | str, *, max_spaces: int = 10_000,
        max_objects: int = 1_000_000, max_scene_page: int = 500,
    ) -> None:
        self.path = Path(state_path)
        if min(max_spaces, max_objects, max_scene_page) <= 0:
            raise ValueError("world resource limits must be positive")
        self.max_spaces, self.max_objects = max_spaces, max_objects
        self.max_scene_page = max_scene_page
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS world_space (
                    space_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    parent_space_id TEXT REFERENCES world_space(space_id),
                    archived INTEGER NOT NULL, revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_space_scope
                    ON world_space(owner_principal_id,audience_id,archived,space_id);
                CREATE TABLE IF NOT EXISTS world_connection (
                    connection_id TEXT PRIMARY KEY,
                    source_space_id TEXT NOT NULL REFERENCES world_space(space_id),
                    target_space_id TEXT NOT NULL REFERENCES world_space(space_id),
                    kind TEXT NOT NULL, label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(source_space_id,target_space_id,kind)
                );
                CREATE TABLE IF NOT EXISTS world_object (
                    object_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    space_id TEXT NOT NULL REFERENCES world_space(space_id),
                    transform_json TEXT NOT NULL, container_id TEXT REFERENCES world_object(object_id),
                    group_id TEXT, asset_id TEXT, state_json TEXT NOT NULL,
                    archived INTEGER NOT NULL, revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS world_object_scene
                    ON world_object(space_id,archived,object_id);
                CREATE INDEX IF NOT EXISTS world_object_container
                    ON world_object(container_id,archived,object_id);
                CREATE TABLE IF NOT EXISTS world_revision (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
                    action TEXT NOT NULL, actor_principal_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    UNIQUE(entity_type,entity_id,revision)
                );
                CREATE TABLE IF NOT EXISTS world_mutation_receipt (
                    receipt_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL, action TEXT NOT NULL,
                    revision INTEGER NOT NULL, actor_principal_id TEXT NOT NULL,
                    evidence_ref TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_interaction_decision (
                    interaction_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL,
                    object_id TEXT NOT NULL REFERENCES world_object(object_id),
                    space_id TEXT NOT NULL REFERENCES world_space(space_id),
                    verb TEXT NOT NULL, gesture TEXT, object_revision INTEGER NOT NULL,
                    evidence_ref TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_interaction_receipt (
                    receipt_id TEXT PRIMARY KEY,
                    interaction_id TEXT NOT NULL REFERENCES world_interaction_decision(interaction_id),
                    status TEXT NOT NULL, renderer_backend TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL, detail TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _moment(value: datetime) -> str:
        return aware(value).astimezone(timezone.utc).isoformat()

    @staticmethod
    def _space(row: sqlite3.Row) -> WorldSpace:
        return WorldSpace(
            row["space_id"], row["name"], SpaceKind(row["kind"]),
            row["owner_principal_id"], row["audience_id"], row["parent_space_id"],
            bool(row["archived"]), int(row["revision"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _object(row: sqlite3.Row) -> WorldObject:
        return WorldObject(
            object_id=row["object_id"], name=row["name"],
            kind=ObjectKind(row["kind"]), owner_principal_id=row["owner_principal_id"],
            audience_id=row["audience_id"], space_id=row["space_id"],
            transform=Transform(**json.loads(row["transform_json"])),
            container_id=row["container_id"], group_id=row["group_id"],
            asset_id=row["asset_id"], state=json.loads(row["state_json"]),
            archived=bool(row["archived"]), revision=int(row["revision"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def ensure_foundation(
        self, *, owner_principal_id: str, audience_id: str, now: datetime,
    ) -> tuple[WorldSpace, ...]:
        """Idempotently create three independent canonical starting spaces."""
        defaults = (
            ("sofia-studio", "Sofía's Studio", SpaceKind.PRIVATE),
            ("engineering-workshop", "Engineering Workshop", SpaceKind.WORKSPACE),
            ("shared-garden", "Shared Garden", SpaceKind.SHARED),
        )
        with closing(self._connect()) as db, db:
            for space_id, name, kind in defaults:
                db.execute(
                    """INSERT OR IGNORE INTO world_space VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (space_id, name, kind.value, owner_principal_id, audience_id,
                     None, 0, 1, self._moment(now), self._moment(now)),
                )
                row = db.execute(
                    "SELECT * FROM world_revision WHERE entity_type='space' AND entity_id=?",
                    (space_id,),
                ).fetchone()
                if row is None:
                    current = db.execute(
                        "SELECT * FROM world_space WHERE space_id=?", (space_id,)
                    ).fetchone()
                    self._revision(
                        db, "space", space_id, 1, dict(current), "initialize",
                        owner_principal_id, "world:foundation", now,
                    )
        return tuple(self.get_space(item[0], owner_principal_id, audience_id) for item in defaults)

    @staticmethod
    def _revision(
        db, entity_type, entity_id, revision, snapshot, action,
        actor_principal_id, evidence_ref, occurred_at,
    ) -> WorldMutationReceipt:
        receipt = WorldMutationReceipt(
            f"world-receipt:{uuid4()}", entity_type, entity_id, action,
            revision, actor_principal_id, evidence_ref, aware(occurred_at),
        )
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        moment = occurred_at.astimezone(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO world_revision(entity_type,entity_id,revision,snapshot_json,action,actor_principal_id,evidence_ref,occurred_at) VALUES(?,?,?,?,?,?,?,?)",
            (entity_type, entity_id, revision, encoded, action,
             actor_principal_id, evidence_ref, moment),
        )
        db.execute(
            "INSERT INTO world_mutation_receipt VALUES(?,?,?,?,?,?,?,?)",
            (receipt.receipt_id, entity_type, entity_id, action, revision,
             actor_principal_id, evidence_ref, moment),
        )
        return receipt

    def _check_scope(self, row, principal_id: str, audience_id: str) -> None:
        if row is None or row["owner_principal_id"] != principal_id or row["audience_id"] != audience_id:
            raise KeyError("world entity is unavailable in this principal/audience scope")

    def get_space(self, space_id: str, principal_id: str, audience_id: str) -> WorldSpace:
        world_id(space_id, "space_id")
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM world_space WHERE space_id=?", (space_id,)).fetchone()
        self._check_scope(row, principal_id, audience_id)
        return self._space(row)

    def create_space(
        self, *, space_id: str, name: str, kind: SpaceKind,
        owner_principal_id: str, audience_id: str, parent_space_id: str | None,
        actor_principal_id: str, evidence_ref: str, now: datetime,
    ) -> WorldMutationReceipt:
        world_id(space_id, "space_id"); bounded_text(name, "space name")
        world_id(owner_principal_id, "owner_principal_id")
        world_id(actor_principal_id, "actor_principal_id")
        bounded_text(audience_id, "audience_id", 160)
        bounded_text(evidence_ref, "evidence_ref", 300)
        if not isinstance(kind, SpaceKind):
            raise TypeError("kind must be SpaceKind")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM world_space").fetchone()[0] >= self.max_spaces:
                raise RuntimeError("world space resource limit exceeded")
            if parent_space_id is not None:
                parent = db.execute("SELECT * FROM world_space WHERE space_id=?", (parent_space_id,)).fetchone()
                self._check_scope(parent, owner_principal_id, audience_id)
            moment = self._moment(now)
            db.execute(
                "INSERT INTO world_space VALUES(?,?,?,?,?,?,?,?,?,?)",
                (space_id, name.strip(), kind.value, owner_principal_id, audience_id,
                 parent_space_id, 0, 1, moment, moment),
            )
            row = dict(db.execute("SELECT * FROM world_space WHERE space_id=?", (space_id,)).fetchone())
            return self._revision(db, "space", space_id, 1, row, "create", actor_principal_id, evidence_ref, now)

    def list_spaces(
        self, principal_id: str, audience_id: str, *, include_archived: bool = False,
    ) -> tuple[WorldSpace, ...]:
        query = "SELECT * FROM world_space WHERE owner_principal_id=? AND audience_id=?"
        params: list[object] = [principal_id, audience_id]
        if not include_archived:
            query += " AND archived=0"
        query += " ORDER BY space_id"
        with closing(self._connect()) as db:
            return tuple(self._space(row) for row in db.execute(query, params))

    def add_object(
        self, value: WorldObject, *, actor_principal_id: str,
        evidence_ref: str, now: datetime,
    ) -> WorldMutationReceipt:
        if not isinstance(value, WorldObject):
            raise TypeError("WorldObject required")
        world_id(actor_principal_id, "actor_principal_id")
        bounded_text(evidence_ref, "evidence_ref", 300)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM world_object").fetchone()[0] >= self.max_objects:
                raise RuntimeError("world object resource limit exceeded")
            space = db.execute("SELECT * FROM world_space WHERE space_id=?", (value.space_id,)).fetchone()
            self._check_scope(space, value.owner_principal_id, value.audience_id)
            if value.container_id is not None:
                container = db.execute("SELECT * FROM world_object WHERE object_id=?", (value.container_id,)).fetchone()
                self._check_scope(container, value.owner_principal_id, value.audience_id)
                if container["kind"] != ObjectKind.CONTAINER.value:
                    raise ValueError("container_id must reference a container object")
            moment = self._moment(now)
            db.execute(
                """INSERT INTO world_object VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (value.object_id, value.name, value.kind.value,
                 value.owner_principal_id, value.audience_id, value.space_id,
                 json.dumps(asdict(value.transform), sort_keys=True),
                 value.container_id, value.group_id, value.asset_id,
                 json.dumps(dict(value.state), sort_keys=True), int(value.archived),
                 1, moment, moment),
            )
            row = dict(db.execute("SELECT * FROM world_object WHERE object_id=?", (value.object_id,)).fetchone())
            return self._revision(db, "object", value.object_id, 1, row, "create", actor_principal_id, evidence_ref, now)

    def scene(
        self, space_id: str, principal_id: str, audience_id: str, *,
        cursor: str | None = None, render_budget: int = 100,
    ) -> ScenePage:
        if type(render_budget) is not int or not 1 <= render_budget <= self.max_scene_page:
            raise ValueError("render_budget exceeds configured scene page limit")
        space = self.get_space(space_id, principal_id, audience_id)
        if space.archived:
            raise ValueError("archived spaces cannot be rendered")
        params: list[object] = [space_id, principal_id, audience_id]
        cursor_clause = ""
        if cursor is not None:
            world_id(cursor, "cursor")
            cursor_clause = " AND object_id>?"
            params.append(cursor)
        params.append(render_budget + 1)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM world_object WHERE space_id=?
                AND owner_principal_id=? AND audience_id=? AND archived=0
                AND container_id IS NULL""" + cursor_clause +
                " ORDER BY object_id LIMIT ?", params,
            ).fetchall()
            total = int(db.execute(
                "SELECT COUNT(*) FROM world_object WHERE space_id=? AND archived=0",
                (space_id,),
            ).fetchone()[0])
        visible = rows[:render_budget]
        next_cursor = visible[-1]["object_id"] if len(rows) > render_budget else None
        return ScenePage(space, tuple(self._object(row) for row in visible), next_cursor, total, render_budget)

    def object_count(self) -> int:
        with closing(self._connect()) as db:
            return int(db.execute("SELECT COUNT(*) FROM world_object").fetchone()[0])

    def get_object(self, object_id: str, principal_id: str, audience_id: str) -> WorldObject:
        world_id(object_id, "object_id")
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM world_object WHERE object_id=?", (object_id,)).fetchone()
        self._check_scope(row, principal_id, audience_id)
        return self._object(row)

    def update_space(
        self, *, space_id: str, owner_principal_id: str, audience_id: str,
        expected_revision: int, actor_principal_id: str, evidence_ref: str,
        now: datetime, name: str | None = None, parent_space_id: str | None = None,
        set_parent: bool = False, archived: bool | None = None,
    ) -> WorldMutationReceipt:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM world_space WHERE space_id=?", (space_id,)).fetchone()
            self._check_scope(row, owner_principal_id, audience_id)
            if int(row["revision"]) != expected_revision:
                raise RuntimeError("space revision changed; reload before editing")
            next_name = row["name"] if name is None else bounded_text(name, "space name")
            next_parent = row["parent_space_id"] if not set_parent else parent_space_id
            if next_parent == space_id:
                raise ValueError("a space cannot parent itself")
            if next_parent is not None:
                parent = db.execute("SELECT * FROM world_space WHERE space_id=?", (next_parent,)).fetchone()
                self._check_scope(parent, owner_principal_id, audience_id)
                ancestor = next_parent
                while ancestor is not None:
                    if ancestor == space_id:
                        raise ValueError("space hierarchy cycle rejected")
                    parent_row = db.execute(
                        "SELECT parent_space_id FROM world_space WHERE space_id=?", (ancestor,)
                    ).fetchone()
                    ancestor = None if parent_row is None else parent_row[0]
            next_archived = int(row["archived"] if archived is None else archived)
            revision = expected_revision + 1
            db.execute(
                """UPDATE world_space SET name=?,parent_space_id=?,archived=?,
                revision=?,updated_at=? WHERE space_id=?""",
                (next_name, next_parent, next_archived, revision,
                 self._moment(now), space_id),
            )
            snapshot = dict(db.execute("SELECT * FROM world_space WHERE space_id=?", (space_id,)).fetchone())
            action = "archive" if archived is True else "restore" if archived is False else "edit"
            return self._revision(
                db, "space", space_id, revision, snapshot, action,
                actor_principal_id, evidence_ref, now,
            )

    def update_object(
        self, *, object_id: str, owner_principal_id: str, audience_id: str,
        expected_revision: int, actor_principal_id: str, evidence_ref: str,
        now: datetime, transform: Transform | None = None,
        container_id: str | None = None, set_container: bool = False,
        group_id: str | None = None, set_group: bool = False,
        state: dict[str, object] | None = None, archived: bool | None = None,
        space_id: str | None = None,
    ) -> WorldMutationReceipt:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM world_object WHERE object_id=?", (object_id,)).fetchone()
            self._check_scope(row, owner_principal_id, audience_id)
            if int(row["revision"]) != expected_revision:
                raise RuntimeError("object revision changed; reload before editing")
            next_space = row["space_id"] if space_id is None else space_id
            target_space = db.execute("SELECT * FROM world_space WHERE space_id=?", (next_space,)).fetchone()
            self._check_scope(target_space, owner_principal_id, audience_id)
            next_container = row["container_id"] if not set_container else container_id
            if next_container is not None:
                if next_container == object_id:
                    raise ValueError("an object cannot contain itself")
                target = db.execute("SELECT * FROM world_object WHERE object_id=?", (next_container,)).fetchone()
                self._check_scope(target, owner_principal_id, audience_id)
                if target["kind"] != ObjectKind.CONTAINER.value:
                    raise ValueError("container_id must reference a container object")
                ancestor = next_container
                while ancestor is not None:
                    if ancestor == object_id:
                        raise ValueError("container cycle rejected")
                    parent = db.execute(
                        "SELECT container_id FROM world_object WHERE object_id=?", (ancestor,)
                    ).fetchone()
                    ancestor = None if parent is None else parent[0]
            next_transform = row["transform_json"] if transform is None else json.dumps(
                asdict(transform), sort_keys=True,
            )
            next_group = row["group_id"] if not set_group else group_id
            if next_group is not None:
                world_id(next_group, "group_id")
            next_state = row["state_json"] if state is None else json.dumps(state, sort_keys=True)
            next_archived = int(row["archived"] if archived is None else archived)
            revision = expected_revision + 1
            db.execute(
                """UPDATE world_object SET space_id=?,transform_json=?,container_id=?,
                group_id=?,state_json=?,archived=?,revision=?,updated_at=? WHERE object_id=?""",
                (next_space, next_transform, next_container, next_group, next_state,
                 next_archived, revision, self._moment(now), object_id),
            )
            snapshot = dict(db.execute("SELECT * FROM world_object WHERE object_id=?", (object_id,)).fetchone())
            action = "archive" if archived is True else "restore" if archived is False else "edit"
            return self._revision(
                db, "object", object_id, revision, snapshot, action,
                actor_principal_id, evidence_ref, now,
            )

    def connect_spaces(
        self, *, connection_id: str, source_space_id: str, target_space_id: str,
        owner_principal_id: str, audience_id: str, kind: str, label: str,
        actor_principal_id: str, evidence_ref: str, now: datetime,
    ) -> WorldMutationReceipt:
        for value, name in ((connection_id, "connection_id"),
                            (source_space_id, "source_space_id"),
                            (target_space_id, "target_space_id")):
            world_id(value, name)
        if source_space_id == target_space_id:
            raise ValueError("connection requires two different spaces")
        bounded_text(kind, "connection kind", 80); bounded_text(label, "connection label")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            for space_id in (source_space_id, target_space_id):
                self._check_scope(
                    db.execute("SELECT * FROM world_space WHERE space_id=?", (space_id,)).fetchone(),
                    owner_principal_id, audience_id,
                )
            moment = self._moment(now)
            db.execute(
                "INSERT INTO world_connection VALUES(?,?,?,?,?,?)",
                (connection_id, source_space_id, target_space_id, kind, label, moment),
            )
            snapshot = dict(db.execute(
                "SELECT * FROM world_connection WHERE connection_id=?", (connection_id,)
            ).fetchone())
            return self._revision(
                db, "connection", connection_id, 1, snapshot, "connect",
                actor_principal_id, evidence_ref, now,
            )

    def inventory(
        self, container_id: str, principal_id: str, audience_id: str, *, limit: int = 200,
    ) -> tuple[WorldObject, ...]:
        if type(limit) is not int or not 1 <= limit <= self.max_scene_page:
            raise ValueError("inventory limit exceeds configured page limit")
        container = self.get_object(container_id, principal_id, audience_id)
        if container.kind is not ObjectKind.CONTAINER:
            raise ValueError("inventory target is not a container")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM world_object WHERE container_id=? AND archived=0
                AND owner_principal_id=? AND audience_id=? ORDER BY object_id LIMIT ?""",
                (container_id, principal_id, audience_id, limit),
            ).fetchall()
        return tuple(self._object(row) for row in rows)

    def history(self, entity_type: str, entity_id: str) -> tuple[dict, ...]:
        if entity_type not in {"space", "object", "connection"}:
            raise ValueError("unsupported world entity type")
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT revision,action,actor_principal_id,evidence_ref,occurred_at
                FROM world_revision WHERE entity_type=? AND entity_id=? ORDER BY revision""",
                (entity_type, entity_id),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def undo(
        self, *, entity_type: str, entity_id: str, target_revision: int,
        owner_principal_id: str, audience_id: str, expected_revision: int,
        actor_principal_id: str, evidence_ref: str, now: datetime,
    ) -> WorldMutationReceipt:
        """Restore a prior snapshot as a new revision; history is never erased."""
        if entity_type not in {"space", "object"}:
            raise ValueError("only spaces and objects support undo")
        if type(target_revision) is not int or target_revision < 1:
            raise ValueError("target_revision must be positive")
        table = f"world_{entity_type}"
        id_column = f"{entity_type}_id"
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                f"SELECT * FROM {table} WHERE {id_column}=?", (entity_id,)
            ).fetchone()
            self._check_scope(current, owner_principal_id, audience_id)
            if int(current["revision"]) != expected_revision:
                raise RuntimeError(f"{entity_type} revision changed; reload before undo")
            prior = db.execute(
                """SELECT snapshot_json FROM world_revision
                WHERE entity_type=? AND entity_id=? AND revision=?""",
                (entity_type, entity_id, target_revision),
            ).fetchone()
            if prior is None:
                raise KeyError("requested world revision does not exist")
            snapshot = json.loads(prior[0])
            if (
                snapshot[id_column] != entity_id
                or snapshot["owner_principal_id"] != owner_principal_id
                or snapshot["audience_id"] != audience_id
            ):
                raise PermissionError("prior snapshot does not match current scope")
            revision = expected_revision + 1
            updated_at = self._moment(now)
            if entity_type == "space":
                db.execute(
                    """UPDATE world_space SET name=?,kind=?,parent_space_id=?,archived=?,
                    revision=?,updated_at=? WHERE space_id=?""",
                    (snapshot["name"], snapshot["kind"], snapshot["parent_space_id"],
                     snapshot["archived"], revision, updated_at, entity_id),
                )
            else:
                db.execute(
                    """UPDATE world_object SET name=?,kind=?,space_id=?,transform_json=?,
                    container_id=?,group_id=?,asset_id=?,state_json=?,archived=?,
                    revision=?,updated_at=? WHERE object_id=?""",
                    (snapshot["name"], snapshot["kind"], snapshot["space_id"],
                     snapshot["transform_json"], snapshot["container_id"],
                     snapshot["group_id"], snapshot["asset_id"],
                     snapshot["state_json"], snapshot["archived"], revision,
                     updated_at, entity_id),
                )
            restored = dict(db.execute(
                f"SELECT * FROM {table} WHERE {id_column}=?", (entity_id,)
            ).fetchone())
            return self._revision(
                db, entity_type, entity_id, revision, restored,
                f"undo-to-{target_revision}", actor_principal_id,
                evidence_ref, now,
            )

    def import_objects(
        self, values: tuple[WorldObject, ...], *, actor_principal_id: str,
        evidence_ref: str, now: datetime,
    ) -> tuple[WorldMutationReceipt, ...]:
        """Atomically import already validated metadata; never fetch assets."""
        if not isinstance(values, tuple) or not values:
            raise ValueError("object import requires a nonempty tuple")
        if len(values) > 5_000:
            raise ValueError("one import is limited to 5000 objects")
        if any(not isinstance(value, WorldObject) for value in values):
            raise TypeError("imports must contain WorldObject values")
        if len({value.object_id for value in values}) != len(values):
            raise ValueError("import object IDs must be unique")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            current_count = int(db.execute("SELECT COUNT(*) FROM world_object").fetchone()[0])
            if current_count + len(values) > self.max_objects:
                raise RuntimeError("world object resource limit exceeded")
            imported = {value.object_id: value for value in values}
            for value in values:
                if value.container_id is None:
                    continue
                target = imported.get(value.container_id)
                if target is None:
                    existing = db.execute(
                        "SELECT kind,owner_principal_id,audience_id FROM world_object WHERE object_id=?",
                        (value.container_id,),
                    ).fetchone()
                    if existing is None or existing[0] != ObjectKind.CONTAINER.value or (
                        existing[1], existing[2]
                    ) != (value.owner_principal_id, value.audience_id):
                        raise ValueError("import container is missing, wrong type, or out of scope")
                elif target.kind is not ObjectKind.CONTAINER or (
                    target.owner_principal_id, target.audience_id
                ) != (value.owner_principal_id, value.audience_id):
                    raise ValueError("import container is wrong type or out of scope")
                seen = {value.object_id}
                ancestor = value.container_id
                while ancestor in imported:
                    if ancestor in seen:
                        raise ValueError("import container cycle rejected")
                    seen.add(ancestor)
                    ancestor = imported[ancestor].container_id

            def containment_depth(value: WorldObject) -> int:
                depth, ancestor = 0, value.container_id
                while ancestor in imported:
                    depth += 1
                    ancestor = imported[ancestor].container_id
                return depth

            ordered_values = tuple(sorted(values, key=containment_depth))
            receipts = []
            moment = self._moment(now)
            for value in ordered_values:
                space = db.execute("SELECT * FROM world_space WHERE space_id=?", (value.space_id,)).fetchone()
                self._check_scope(space, value.owner_principal_id, value.audience_id)
                db.execute(
                    """INSERT INTO world_object VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (value.object_id, value.name, value.kind.value,
                     value.owner_principal_id, value.audience_id, value.space_id,
                     json.dumps(asdict(value.transform), sort_keys=True),
                     value.container_id, value.group_id, value.asset_id,
                     json.dumps(dict(value.state), sort_keys=True), int(value.archived),
                     1, moment, moment),
                )
                snapshot = dict(db.execute(
                    "SELECT * FROM world_object WHERE object_id=?", (value.object_id,)
                ).fetchone())
                receipts.append(self._revision(
                    db, "object", value.object_id, 1, snapshot, "import",
                    actor_principal_id, evidence_ref, now,
                ))
            return tuple(receipts)
