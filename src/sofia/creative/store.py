from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from .model import ArtifactKind, ArtifactRevision, CreativeProject


class CreativeStore:
    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS creative_project (
                    project_id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    owner_principal_id TEXT NOT NULL, audience_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, archived INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS creative_artifact_revision (
                    artifact_id TEXT NOT NULL, project_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL, content_path TEXT NOT NULL,
                    media_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
                    tool_id TEXT NOT NULL, tool_version TEXT NOT NULL,
                    preview_sha256 TEXT, test_summary TEXT NOT NULL,
                    license_id TEXT NOT NULL, author_principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL, evidence_ref TEXT NOT NULL,
                    source_receipt_id TEXT, created_at TEXT NOT NULL,
                    PRIMARY KEY(artifact_id,revision),
                    FOREIGN KEY(project_id) REFERENCES creative_project(project_id)
                );
                CREATE INDEX IF NOT EXISTS creative_artifact_project
                    ON creative_artifact_revision(project_id,artifact_id,revision DESC);
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def create_project(self, project: CreativeProject) -> None:
        if not isinstance(project, CreativeProject):
            raise TypeError("CreativeProject required")
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO creative_project VALUES(?,?,?,?,?,?)",
                (project.project_id, project.title, project.owner_principal_id,
                 project.audience_id, project.created_at.isoformat(), int(project.archived)),
            )

    def project(self, project_id: str, owner_id: str, audience_id: str) -> CreativeProject:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM creative_project WHERE project_id=?", (project_id,)).fetchone()
        if row is None or (row["owner_principal_id"], row["audience_id"]) != (owner_id, audience_id):
            raise KeyError("creative project unavailable in this scope")
        return CreativeProject(
            row["project_id"], row["title"], row["owner_principal_id"],
            row["audience_id"], datetime.fromisoformat(row["created_at"]),
            bool(row["archived"]),
        )

    def list_projects(
        self, owner_id: str, audience_id: str, *, include_archived: bool = False,
    ) -> tuple[CreativeProject, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT * FROM creative_project
                WHERE owner_principal_id=? AND audience_id=?
                AND (? OR archived=0) ORDER BY created_at,project_id""",
                (owner_id, audience_id, int(include_archived)),
            ).fetchall()
        return tuple(
            CreativeProject(
                row["project_id"], row["title"], row["owner_principal_id"],
                row["audience_id"], datetime.fromisoformat(row["created_at"]),
                bool(row["archived"]),
            )
            for row in rows
        )

    @staticmethod
    def _decode(row) -> ArtifactRevision:
        return ArtifactRevision(
            row["artifact_id"], row["project_id"], int(row["revision"]),
            ArtifactKind(row["kind"]), row["title"], row["content_sha256"],
            row["content_path"], row["media_type"], int(row["byte_size"]),
            row["tool_id"], row["tool_version"], row["preview_sha256"],
            row["test_summary"], row["license_id"], row["author_principal_id"],
            row["audience_id"], row["evidence_ref"], row["source_receipt_id"],
            datetime.fromisoformat(row["created_at"]),
        )

    def append(self, revision: ArtifactRevision) -> None:
        if not isinstance(revision, ArtifactRevision):
            raise TypeError("ArtifactRevision required")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            project = db.execute(
                "SELECT audience_id,archived FROM creative_project WHERE project_id=?",
                (revision.project_id,),
            ).fetchone()
            if project is None or project["audience_id"] != revision.audience_id:
                raise KeyError("creative project unavailable in this audience scope")
            if bool(project["archived"]):
                raise ValueError("cannot append an artifact to an archived project")
            prior_project = db.execute(
                "SELECT project_id FROM creative_artifact_revision WHERE artifact_id=? LIMIT 1",
                (revision.artifact_id,),
            ).fetchone()
            if prior_project is not None and prior_project["project_id"] != revision.project_id:
                raise ValueError("artifact identity already belongs to another project")
            latest = db.execute(
                "SELECT MAX(revision) FROM creative_artifact_revision WHERE artifact_id=?",
                (revision.artifact_id,),
            ).fetchone()[0]
            expected = 1 if latest is None else int(latest) + 1
            if revision.revision != expected:
                raise RuntimeError("artifact revision is not the next canonical revision")
            db.execute(
                "INSERT INTO creative_artifact_revision VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (revision.artifact_id, revision.project_id, revision.revision,
                 revision.kind.value, revision.title, revision.content_sha256,
                 revision.content_path, revision.media_type, revision.byte_size,
                 revision.tool_id, revision.tool_version, revision.preview_sha256,
                 revision.test_summary, revision.license_id,
                 revision.author_principal_id, revision.audience_id,
                 revision.evidence_ref, revision.source_receipt_id,
                 revision.created_at.isoformat()),
            )

    def latest(self, artifact_id: str, owner_id: str, audience_id: str) -> ArtifactRevision | None:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT a.* FROM creative_artifact_revision a
                JOIN creative_project p ON p.project_id=a.project_id
                WHERE a.artifact_id=? AND p.owner_principal_id=? AND a.audience_id=?
                ORDER BY a.revision DESC LIMIT 1""",
                (artifact_id, owner_id, audience_id),
            ).fetchone()
        return None if row is None else self._decode(row)

    def list_project(self, project_id: str, owner_id: str, audience_id: str) -> tuple[ArtifactRevision, ...]:
        self.project(project_id, owner_id, audience_id)
        with closing(self._connect()) as db:
            rows = db.execute(
                """SELECT a.* FROM creative_artifact_revision a JOIN (
                    SELECT artifact_id,MAX(revision) revision FROM creative_artifact_revision
                    WHERE project_id=? GROUP BY artifact_id
                ) latest ON a.artifact_id=latest.artifact_id AND a.revision=latest.revision
                WHERE a.audience_id=? ORDER BY a.artifact_id""",
                (project_id, audience_id),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)

    def history(self, artifact_id: str, owner_id: str, audience_id: str) -> tuple[ArtifactRevision, ...]:
        latest = self.latest(artifact_id, owner_id, audience_id)
        if latest is None:
            return ()
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT * FROM creative_artifact_revision WHERE artifact_id=? AND audience_id=? ORDER BY revision",
                (artifact_id, audience_id),
            ).fetchall()
        return tuple(self._decode(row) for row in rows)
