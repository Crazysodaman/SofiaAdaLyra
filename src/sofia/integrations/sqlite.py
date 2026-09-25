"""Bounded read-only SQLite inspection adapter."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any

class SQLiteReadAdapter:
    def __init__(self,path:Path)->None:
        self.path=path.resolve()
        if not self.path.exists() or not self.path.is_file(): raise ValueError("SQLite database file must exist")
    def tables(self)->tuple[str,...]:
        with self._connect() as db:
            rows=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        return tuple(str(r[0]) for r in rows)
    def query(self,sql:str,parameters:tuple[Any,...]=(),*,limit:int=200)->tuple[dict[str,Any],...]:
        if not isinstance(sql,str) or not sql.strip(): raise ValueError("SQL required")
        first=sql.lstrip().split(None,1)[0].lower()
        if first not in ("select","pragma","with","explain"): raise PermissionError("SQLiteReadAdapter permits read-only statements only")
        if not 1<=limit<=1000: raise ValueError("limit must be 1..1000")
        with self._connect() as db:
            cur=db.execute(sql,parameters)
            names=tuple(d[0] for d in cur.description or ())
            rows=cur.fetchmany(limit+1)
        if len(rows)>limit: rows=rows[:limit]
        return tuple(dict(zip(names,row)) for row in rows)
    def _connect(self):
        uri=f"file:{self.path.as_posix()}?mode=ro"
        return sqlite3.connect(uri,uri=True,timeout=5)
