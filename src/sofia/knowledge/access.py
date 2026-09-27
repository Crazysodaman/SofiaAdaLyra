from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sqlite3


class KnowledgeVisibility(str,Enum):
    SHARED="shared"
    PRIVATE="private"


@dataclass(frozen=True,slots=True)
class KnowledgeAccess:
    document_id:str
    visibility:KnowledgeVisibility
    principal_id:str|None=None
    audience_id:str|None=None

    def __post_init__(self)->None:
        if not isinstance(self.document_id,str) or not self.document_id.strip():
            raise ValueError("document_id must be nonempty")
        if not isinstance(self.visibility,KnowledgeVisibility):
            raise TypeError("visibility must be KnowledgeVisibility")
        if self.visibility is KnowledgeVisibility.PRIVATE:
            if not isinstance(self.principal_id,str) or not self.principal_id.strip():
                raise ValueError("private knowledge requires principal_id")
            if not isinstance(self.audience_id,str) or not self.audience_id.strip():
                raise ValueError("private knowledge requires audience_id")


class KnowledgeAccessStore:
    """Audience policy for knowledge documents. Missing rows fail closed."""

    def __init__(self,state_path:Path|str)->None:
        self.path=Path(state_path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_access (
                    document_id TEXT PRIMARY KEY,
                    visibility TEXT NOT NULL CHECK(visibility IN ('shared','private')),
                    principal_id TEXT,
                    audience_id TEXT
                )
            """)

    def set(self,access:KnowledgeAccess)->KnowledgeAccess:
        if not isinstance(access,KnowledgeAccess):
            raise TypeError("access must be KnowledgeAccess")
        with sqlite3.connect(self.path,timeout=10) as db:
            db.execute("""
                INSERT INTO knowledge_access(
                    document_id,visibility,principal_id,audience_id
                ) VALUES(?,?,?,?)
                ON CONFLICT(document_id) DO UPDATE SET
                    visibility=excluded.visibility,
                    principal_id=excluded.principal_id,
                    audience_id=excluded.audience_id
            """,(
                access.document_id,
                access.visibility.value,
                access.principal_id,
                access.audience_id,
            ))
        return access

    def get(self,document_id:str)->KnowledgeAccess|None:
        if not isinstance(document_id,str) or not document_id.strip():
            raise ValueError("document_id must be nonempty")
        with sqlite3.connect(self.path,timeout=10) as db:
            row=db.execute("""
                SELECT document_id,visibility,principal_id,audience_id
                FROM knowledge_access WHERE document_id=?
            """,(document_id,)).fetchone()
        if row is None:
            return None
        return KnowledgeAccess(
            document_id=row[0],
            visibility=KnowledgeVisibility(row[1]),
            principal_id=row[2],
            audience_id=row[3],
        )

    def permitted(
        self,
        document_id:str,
        *,
        principal_id:str|None,
        audience_id:str|None,
    )->bool:
        access=self.get(document_id)
        if access is None:
            return False
        if access.visibility is KnowledgeVisibility.SHARED:
            return True
        return (
            principal_id is not None
            and audience_id is not None
            and access.principal_id==principal_id
            and access.audience_id==audience_id
        )
