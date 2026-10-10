"""Canonical SQLite persistence for independent-life projects and experiences."""
from __future__ import annotations

from contextlib import closing
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3

from .model import (
    ArtifactEvaluation, ExperienceRecord, InterestRecord, InterestStatus,
    LifeProject, LifeSelection, MilestoneStatus, PersonalJudgment,
    ProjectBrief, ProjectEvent, ProjectMilestone, ProjectScope, ProjectStatus,
    ResourceBudget, SelectionKind, TechnicalOutcome,
)


class LifeStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        if not self.path.is_file():
            raise FileNotFoundError("canonical sofia.db is required")
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS life_project (
                    project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    description TEXT NOT NULL, creator_principal_id TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    scope TEXT NOT NULL, originating_interest TEXT NOT NULL,
                    status TEXT NOT NULL, brief_json TEXT NOT NULL, goal_id TEXT,
                    priority REAL NOT NULL, confidence REAL NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL, superseded_by TEXT
                );
                CREATE INDEX IF NOT EXISTS life_project_scope
                    ON life_project(owner_principal_id,audience_id,status,priority DESC);
                CREATE TABLE IF NOT EXISTS life_project_event (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL,
                    from_status TEXT, to_status TEXT NOT NULL,
                    decision TEXT NOT NULL, reason TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL, actor_principal_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_project_artifact (
                    project_id TEXT NOT NULL, artifact_id TEXT NOT NULL,
                    artifact_revision INTEGER NOT NULL, linked_at TEXT NOT NULL,
                    PRIMARY KEY(project_id,artifact_id,artifact_revision),
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_project_milestone (
                    milestone_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    title TEXT NOT NULL, status TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    evidence_refs_json TEXT NOT NULL, result TEXT,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id,ordinal),
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_project_space (
                    project_id TEXT NOT NULL, space_id TEXT NOT NULL,
                    linked_at TEXT NOT NULL, PRIMARY KEY(project_id,space_id),
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_project_job (
                    project_id TEXT NOT NULL, job_id TEXT NOT NULL UNIQUE,
                    linked_at TEXT NOT NULL, PRIMARY KEY(project_id,job_id),
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_artifact_evaluation (
                    evaluation_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL, artifact_revision INTEGER NOT NULL,
                    technical_outcome TEXT NOT NULL, personal_judgment TEXT NOT NULL,
                    objective_results_json TEXT NOT NULL, reason TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL, preserve_for_research INTEGER NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE TABLE IF NOT EXISTS life_experience (
                    experience_id TEXT PRIMARY KEY, project_id TEXT,
                    kind TEXT NOT NULL, summary TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL, audience_id TEXT NOT NULL,
                    private INTEGER NOT NULL, occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, metadata_json TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES life_project(project_id)
                );
                CREATE INDEX IF NOT EXISTS life_experience_scope
                    ON life_experience(audience_id,private,occurred_at DESC);
                CREATE TABLE IF NOT EXISTS life_selection (
                    selection_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    project_id TEXT, reason TEXT NOT NULL,
                    resource_pressure REAL NOT NULL, busy INTEGER NOT NULL,
                    selected_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS life_interest_revision (
                    interest_id TEXT NOT NULL, name TEXT NOT NULL,
                    context TEXT NOT NULL, strength REAL NOT NULL,
                    confidence REAL NOT NULL, status TEXT NOT NULL,
                    reason TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
                    audience_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(interest_id,revision),
                    UNIQUE(name,context,audience_id,revision)
                );
                CREATE TABLE IF NOT EXISTS life_quiet_choice (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    until_at TEXT NOT NULL, reason TEXT NOT NULL,
                    chosen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS life_resource_usage (
                    project_id TEXT NOT NULL, usage_day TEXT NOT NULL,
                    cpu_seconds REAL NOT NULL, gpu_seconds REAL NOT NULL,
                    wall_seconds REAL NOT NULL, storage_bytes INTEGER NOT NULL,
                    job_count INTEGER NOT NULL,
                    PRIMARY KEY(project_id,usage_day)
                );
                CREATE TABLE IF NOT EXISTS life_idea_attempt (
                    slot_key TEXT PRIMARY KEY, attempted_at TEXT NOT NULL,
                    status TEXT NOT NULL, reason TEXT NOT NULL,
                    suggestion_id TEXT, project_id TEXT
                );
                CREATE TABLE IF NOT EXISTS life_artifact_authorization (
                    request_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL, request_digest TEXT NOT NULL,
                    status TEXT NOT NULL, authorized_at TEXT NOT NULL,
                    finished_at TEXT
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _brief(value: ProjectBrief) -> str:
        budget = value.resource_budget
        return json.dumps({
            "objectives": value.objectives,
            "optional_success_criteria": value.optional_success_criteria,
            "required_tools": value.required_tools,
            "permission_requirements": value.permission_requirements,
            "resource_budget": {
                "cpu_percent": budget.cpu_percent,
                "gpu_percent": budget.gpu_percent,
                "memory_mb": budget.memory_mb,
                "storage_bytes": budget.storage_bytes,
                "daily_seconds": budget.daily_seconds,
                "concurrent_jobs": budget.concurrent_jobs,
            },
            "associated_space_ids": value.associated_space_ids,
        }, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _project(row: sqlite3.Row) -> LifeProject:
        value = json.loads(row["brief_json"])
        brief = ProjectBrief(
            tuple(value["objectives"]), tuple(value["optional_success_criteria"]),
            tuple(value["required_tools"]), tuple(value["permission_requirements"]),
            ResourceBudget(**value["resource_budget"]),
            tuple(value.get("associated_space_ids", ())),
        )
        return LifeProject(
            row["project_id"], row["name"], row["description"],
            row["creator_principal_id"], row["owner_principal_id"],
            row["audience_id"], ProjectScope(row["scope"]),
            row["originating_interest"], ProjectStatus(row["status"]), brief,
            row["goal_id"], float(row["priority"]), float(row["confidence"]),
            datetime.fromisoformat(row["created_at"]),
            datetime.fromisoformat(row["updated_at"]), int(row["revision"]),
            row["superseded_by"],
        )

    @staticmethod
    def _values(project: LifeProject) -> tuple[object, ...]:
        return (
            project.project_id, project.name, project.description,
            project.creator_principal_id, project.owner_principal_id,
            project.audience_id, project.scope.value,
            project.originating_interest, project.status.value,
            LifeStore._brief(project.brief), project.goal_id,
            project.priority, project.confidence,
            project.created_at.astimezone(timezone.utc).isoformat(),
            project.updated_at.astimezone(timezone.utc).isoformat(),
            project.revision, project.superseded_by,
        )

    @staticmethod
    def _insert_event(db: sqlite3.Connection, event: ProjectEvent) -> None:
        db.execute(
            """INSERT INTO life_project_event(
            event_id,project_id,from_status,to_status,decision,reason,
            evidence_refs_json,actor_principal_id,occurred_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                event.event_id, event.project_id,
                None if event.from_status is None else event.from_status.value,
                event.to_status.value, event.decision, event.reason,
                json.dumps(event.evidence_refs), event.actor_principal_id,
                event.occurred_at.astimezone(timezone.utc).isoformat(),
            ),
        )

    def create(self, project: LifeProject, event: ProjectEvent) -> LifeProject:
        if not isinstance(project, LifeProject) or not isinstance(event, ProjectEvent):
            raise TypeError("LifeProject and ProjectEvent required")
        if event.project_id != project.project_id or event.from_status is not None or event.to_status is not project.status:
            raise ValueError("initial project event does not match project")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO life_project VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", self._values(project))
            self._insert_event(db, event)
        return project

    def get(self, project_id: str, *, owner_principal_id: str, audience_id: str) -> LifeProject:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM life_project WHERE project_id=?", (project_id,)).fetchone()
        if row is None or (row["owner_principal_id"], row["audience_id"]) != (owner_principal_id, audience_id):
            raise KeyError("project unavailable in this owner/audience scope")
        return self._project(row)

    def list_scope(
        self, *, owner_principal_id: str, audience_id: str,
        statuses: tuple[ProjectStatus, ...] | None = None,
    ) -> tuple[LifeProject, ...]:
        query = "SELECT * FROM life_project WHERE owner_principal_id=? AND audience_id=?"
        parameters: list[object] = [owner_principal_id, audience_id]
        if statuses is not None:
            if not statuses:
                return ()
            query += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            parameters.extend(status.value for status in statuses)
        query += " ORDER BY priority DESC,updated_at,project_id"
        with closing(self._connect()) as db:
            rows = db.execute(query, parameters).fetchall()
        return tuple(self._project(row) for row in rows)

    def update(self, project: LifeProject, event: ProjectEvent, *, expected_revision: int) -> LifeProject:
        if event.project_id != project.project_id or event.to_status is not project.status:
            raise ValueError("project event does not match update")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision,status FROM life_project WHERE project_id=?", (project.project_id,)).fetchone()
            if row is None or int(row["revision"]) != expected_revision or row["status"] != event.from_status.value:
                raise RuntimeError("project changed concurrently")
            changed = db.execute(
                """UPDATE life_project SET name=?,description=?,creator_principal_id=?,
                owner_principal_id=?,audience_id=?,scope=?,originating_interest=?,status=?,
                brief_json=?,goal_id=?,priority=?,confidence=?,created_at=?,updated_at=?,
                revision=?,superseded_by=? WHERE project_id=? AND revision=?""",
                self._values(project)[1:] + (project.project_id, expected_revision),
            )
            if changed.rowcount != 1:
                raise RuntimeError("project update lost compare-and-swap")
            self._insert_event(db, event)
        return project

    def events(self, project_id: str, *, owner_principal_id: str, audience_id: str) -> tuple[ProjectEvent, ...]:
        self.get(project_id, owner_principal_id=owner_principal_id, audience_id=audience_id)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM life_project_event WHERE project_id=? ORDER BY sequence",
                (project_id,),
            ).fetchall()
        return tuple(ProjectEvent(
            row["event_id"], row["project_id"],
            None if row["from_status"] is None else ProjectStatus(row["from_status"]),
            ProjectStatus(row["to_status"]), row["decision"], row["reason"],
            tuple(json.loads(row["evidence_refs_json"])), row["actor_principal_id"],
            datetime.fromisoformat(row["occurred_at"]),
        ) for row in rows)

    def link_artifact(self, project_id: str, artifact_id: str, revision: int, *, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO life_project_artifact VALUES(?,?,?,?)",
                (project_id, artifact_id, revision, now.astimezone(timezone.utc).isoformat()),
            )

    def artifacts(self, project_id: str) -> tuple[tuple[str, int], ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT artifact_id,artifact_revision FROM life_project_artifact WHERE project_id=? ORDER BY linked_at",
                (project_id,),
            ).fetchall()
        return tuple((row[0], int(row[1])) for row in rows)

    def add_milestone(self, value: ProjectMilestone) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO life_project_milestone VALUES(?,?,?,?,?,?,?,?)",
                (value.milestone_id, value.project_id, value.title,
                 value.status.value, value.ordinal,
                 json.dumps(value.evidence_refs), value.result,
                 value.updated_at.astimezone(timezone.utc).isoformat()),
            )

    def update_milestone(
        self, value: ProjectMilestone, *, expected_status: MilestoneStatus,
    ) -> None:
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE life_project_milestone SET status=?,evidence_refs_json=?,
                result=?,updated_at=? WHERE milestone_id=? AND status=?""",
                (value.status.value, json.dumps(value.evidence_refs), value.result,
                 value.updated_at.astimezone(timezone.utc).isoformat(),
                 value.milestone_id, expected_status.value),
            )
            if changed.rowcount != 1:
                raise RuntimeError("milestone changed concurrently")

    def milestones(self, project_id: str) -> tuple[ProjectMilestone, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM life_project_milestone WHERE project_id=? ORDER BY ordinal",
                (project_id,),
            ).fetchall()
        return tuple(ProjectMilestone(
            row["milestone_id"], row["project_id"], row["title"],
            MilestoneStatus(row["status"]), int(row["ordinal"]),
            tuple(json.loads(row["evidence_refs_json"])), row["result"],
            datetime.fromisoformat(row["updated_at"]),
        ) for row in rows)

    def link_space(self, project_id: str, space_id: str, *, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO life_project_space VALUES(?,?,?)",
                (project_id, space_id, now.astimezone(timezone.utc).isoformat()),
            )

    def spaces(self, project_id: str) -> tuple[str, ...]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT space_id FROM life_project_space WHERE project_id=? ORDER BY linked_at", (project_id,)).fetchall()
        return tuple(row[0] for row in rows)

    def link_job(self, project_id: str, job_id: str, *, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR IGNORE INTO life_project_job VALUES(?,?,?)",
                (project_id, job_id, now.astimezone(timezone.utc).isoformat()),
            )

    def jobs(self, project_id: str) -> tuple[str, ...]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT job_id FROM life_project_job WHERE project_id=? ORDER BY linked_at", (project_id,)).fetchall()
        return tuple(row[0] for row in rows)

    def record_evaluation(self, value: ArtifactEvaluation) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO life_artifact_evaluation VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    value.evaluation_id, value.project_id, value.artifact_id,
                    value.artifact_revision, value.technical_outcome.value,
                    value.personal_judgment.value,
                    json.dumps(dict(value.objective_results), sort_keys=True),
                    value.reason, json.dumps(value.evidence_refs),
                    int(value.preserve_for_research),
                    value.evaluated_at.astimezone(timezone.utc).isoformat(),
                ),
            )

    def evaluations(self, project_id: str) -> tuple[ArtifactEvaluation, ...]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM life_artifact_evaluation WHERE project_id=? ORDER BY evaluated_at,evaluation_id", (project_id,)).fetchall()
        return tuple(ArtifactEvaluation(
            row["evaluation_id"], row["project_id"], row["artifact_id"],
            int(row["artifact_revision"]), TechnicalOutcome(row["technical_outcome"]),
            PersonalJudgment(row["personal_judgment"]),
            json.loads(row["objective_results_json"]), row["reason"],
            tuple(json.loads(row["evidence_refs_json"])),
            bool(row["preserve_for_research"]),
            datetime.fromisoformat(row["evaluated_at"]),
        ) for row in rows)

    def record_experience(self, value: ExperienceRecord) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO life_experience VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    value.experience_id, value.project_id, value.kind, value.summary,
                    json.dumps(value.evidence_refs), value.audience_id,
                    int(value.private), value.occurred_at.astimezone(timezone.utc).isoformat(),
                    value.recorded_at.astimezone(timezone.utc).isoformat(),
                    json.dumps(dict(value.metadata), sort_keys=True),
                ),
            )

    def experiences(self, *, audience_id: str, include_private: bool, limit: int = 100) -> tuple[ExperienceRecord, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("experience limit must be in 1..500")
        query = "SELECT * FROM life_experience WHERE audience_id=?"
        parameters: list[object] = [audience_id]
        if not include_private:
            query += " AND private=0"
        query += " ORDER BY occurred_at DESC,experience_id DESC LIMIT ?"
        parameters.append(limit)
        with closing(self._connect()) as db:
            rows = db.execute(query, parameters).fetchall()
        return tuple(ExperienceRecord(
            row["experience_id"], row["project_id"], row["kind"], row["summary"],
            tuple(json.loads(row["evidence_refs_json"])), row["audience_id"],
            bool(row["private"]), datetime.fromisoformat(row["occurred_at"]),
            datetime.fromisoformat(row["recorded_at"]), json.loads(row["metadata_json"]),
        ) for row in rows)

    def record_selection(self, value: LifeSelection) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO life_selection VALUES(?,?,?,?,?,?,?)",
                (value.selection_id, value.kind.value, value.project_id, value.reason,
                 value.resource_pressure, int(value.busy),
                 value.selected_at.astimezone(timezone.utc).isoformat()),
            )
            db.execute(
                """DELETE FROM life_selection WHERE selection_id IN (
                SELECT selection_id FROM life_selection
                ORDER BY selected_at DESC,selection_id DESC LIMIT -1 OFFSET 5000
                )"""
            )

    def revise_interest(self, value: InterestRecord, *, expected_revision: int | None) -> None:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """SELECT revision FROM life_interest_revision
                WHERE name=? AND context=? AND audience_id=?
                ORDER BY revision DESC LIMIT 1""",
                (value.name, value.context, value.audience_id),
            ).fetchone()
            current = None if row is None else int(row[0])
            if current != expected_revision or value.revision != (1 if current is None else current + 1):
                raise RuntimeError("interest changed concurrently")
            db.execute(
                "INSERT INTO life_interest_revision VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (value.interest_id, value.name, value.context, value.strength,
                 value.confidence, value.status.value, value.reason,
                 json.dumps(value.evidence_refs), value.audience_id,
                 value.revision, value.recorded_at.astimezone(timezone.utc).isoformat()),
            )

    def current_interest(self, *, name: str, context: str, audience_id: str) -> InterestRecord | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT * FROM life_interest_revision WHERE name=? AND context=?
                AND audience_id=? ORDER BY revision DESC LIMIT 1""",
                (name, context, audience_id),
            ).fetchone()
        return None if row is None else InterestRecord(
            row["interest_id"], row["name"], row["context"],
            float(row["strength"]), float(row["confidence"]),
            InterestStatus(row["status"]), row["reason"],
            tuple(json.loads(row["evidence_refs_json"])), row["audience_id"],
            int(row["revision"]), datetime.fromisoformat(row["recorded_at"]),
        )

    def active_interests(self, *, audience_id: str) -> tuple[InterestRecord, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT current.* FROM life_interest_revision current
                JOIN (SELECT name,context,MAX(revision) revision
                      FROM life_interest_revision WHERE audience_id=?
                      GROUP BY name,context) latest
                ON current.name=latest.name AND current.context=latest.context
                AND current.revision=latest.revision
                WHERE current.audience_id=? AND current.status='active'
                ORDER BY current.strength DESC,current.name""",
                (audience_id, audience_id),
            ).fetchall()
        return tuple(InterestRecord(
            row["interest_id"], row["name"], row["context"],
            float(row["strength"]), float(row["confidence"]),
            InterestStatus(row["status"]), row["reason"],
            tuple(json.loads(row["evidence_refs_json"])), row["audience_id"],
            int(row["revision"]), datetime.fromisoformat(row["recorded_at"]),
        ) for row in rows)

    def selections(self, *, limit: int = 100) -> tuple[LifeSelection, ...]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM life_selection ORDER BY selected_at DESC LIMIT ?", (limit,)).fetchall()
        return tuple(LifeSelection(
            row["selection_id"], SelectionKind(row["kind"]), row["project_id"],
            row["reason"], float(row["resource_pressure"]), bool(row["busy"]),
            datetime.fromisoformat(row["selected_at"]),
        ) for row in rows)

    def choose_quiet(self, *, until_at: datetime, reason: str, now: datetime) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT OR REPLACE INTO life_quiet_choice VALUES(1,?,?,?)",
                (until_at.astimezone(timezone.utc).isoformat(), reason,
                 now.astimezone(timezone.utc).isoformat()),
            )

    def quiet_until(self, *, now: datetime) -> tuple[datetime, str] | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT until_at,reason FROM life_quiet_choice WHERE singleton=1").fetchone()
        if row is None:
            return None
        until = datetime.fromisoformat(row[0])
        return None if until <= now else (until, row[1])

    def add_usage(
        self, *, project_id: str, usage_day: date, cpu_seconds: float,
        gpu_seconds: float, wall_seconds: float, storage_bytes: int,
    ) -> None:
        if min(cpu_seconds, gpu_seconds, wall_seconds, storage_bytes) < 0:
            raise ValueError("resource usage cannot be negative")
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO life_resource_usage VALUES(?,?,?,?,?,?,1)
                ON CONFLICT(project_id,usage_day) DO UPDATE SET
                cpu_seconds=cpu_seconds+excluded.cpu_seconds,
                gpu_seconds=gpu_seconds+excluded.gpu_seconds,
                wall_seconds=wall_seconds+excluded.wall_seconds,
                storage_bytes=storage_bytes+excluded.storage_bytes,
                job_count=job_count+1""",
                (project_id, usage_day.isoformat(), cpu_seconds, gpu_seconds,
                 wall_seconds, storage_bytes),
            )

    def usage(self, project_id: str, usage_day: date) -> dict[str, float | int]:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM life_resource_usage WHERE project_id=? AND usage_day=?",
                (project_id, usage_day.isoformat()),
            ).fetchone()
        if row is None:
            return {"cpu_seconds": 0.0, "gpu_seconds": 0.0, "wall_seconds": 0.0, "storage_bytes": 0, "job_count": 0}
        return {key: row[key] for key in ("cpu_seconds", "gpu_seconds", "wall_seconds", "storage_bytes", "job_count")}

    def claim_idea_attempt(self, *, now: datetime) -> str | None:
        slot = now.astimezone(timezone.utc).date().isoformat()
        with closing(self._connect()) as db, db:
            changed = db.execute(
                "INSERT OR IGNORE INTO life_idea_attempt VALUES(?,?,'working','claimed',NULL,NULL)",
                (slot, now.astimezone(timezone.utc).isoformat()),
            )
        return slot if changed.rowcount == 1 else None

    def finish_idea_attempt(
        self, slot_key: str, *, status: str, reason: str,
        suggestion_id: str | None = None, project_id: str | None = None,
    ) -> None:
        if status not in {"accepted", "declined", "failed"}:
            raise ValueError("invalid idea attempt status")
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE life_idea_attempt SET status=?,reason=?,suggestion_id=?,project_id=?
                WHERE slot_key=? AND status='working'""",
                (status, reason, suggestion_id, project_id, slot_key),
            )
            if changed.rowcount != 1:
                raise RuntimeError("idea attempt is not claimable")

    def authorize_artifact(
        self, *, request_id: str, project_id: str, artifact_id: str,
        request_digest: str, now: datetime,
    ) -> None:
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO life_artifact_authorization VALUES(?,?,?,?,'authorized',?,NULL)",
                (request_id, project_id, artifact_id, request_digest,
                 now.astimezone(timezone.utc).isoformat()),
            )

    def claim_artifact_authorization(
        self, request_id: str, project_id: str, artifact_id: str,
        request_digest: str,
    ) -> bool:
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE life_artifact_authorization SET status='claimed'
                WHERE request_id=? AND project_id=? AND artifact_id=?
                  AND request_digest=? AND status='authorized'""",
                (request_id, project_id, artifact_id, request_digest),
            )
        return changed.rowcount == 1

    def finish_artifact_authorization(self, request_id: str, successful: bool) -> None:
        with closing(self._connect()) as db, db:
            changed = db.execute(
                """UPDATE life_artifact_authorization SET status=?,finished_at=?
                WHERE request_id=? AND status='claimed'""",
                ("completed" if successful else "failed",
                 datetime.now(timezone.utc).isoformat(), request_id),
            )
            if changed.rowcount != 1:
                raise RuntimeError("creative execution grant is not claimed")

    def cancel_artifact_authorization(self, request_id: str) -> None:
        """Close an unused grant when outer capability authority denies execution."""
        with closing(self._connect()) as db, db:
            db.execute(
                """UPDATE life_artifact_authorization
                SET status='failed',finished_at=?
                WHERE request_id=? AND status='authorized'""",
                (datetime.now(timezone.utc).isoformat(), request_id),
            )
