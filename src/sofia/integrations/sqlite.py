"""Bounded SQLite inspection and specific maintenance operations."""
from __future__ import annotations
from datetime import datetime,timezone
import sqlite3
from pathlib import Path
from typing import Any

class SQLiteReadAdapter:
    def __init__(self,path:Path)->None:
        self.path=path.resolve()
        if not self.path.exists() or not self.path.is_file(): raise ValueError("SQLite database file must exist")

    def tables(self)->tuple[str,...]:
        with self._connect_ro() as db:
            rows=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        return tuple(str(r[0]) for r in rows)

    def query(self,sql:str,parameters:tuple[Any,...]=(),*,limit:int=200)->tuple[dict[str,Any],...]:
        if not isinstance(sql,str) or not sql.strip(): raise ValueError("SQL required")
        first=sql.lstrip().split(None,1)[0].lower()
        if first not in ("select","pragma","with","explain"): raise PermissionError("SQLiteReadAdapter permits read-only statements only")
        if not 1<=limit<=1000: raise ValueError("limit must be 1..1000")
        with self._connect_ro() as db:
            cur=db.execute(sql,parameters)
            names=tuple(d[0] for d in cur.description or ())
            rows=cur.fetchmany(limit+1)
        if len(rows)>limit: rows=rows[:limit]
        return tuple(dict(zip(names,row)) for row in rows)

    def integrity_check(self)->tuple[str,...]:
        with self._connect_ro() as db:
            rows=db.execute("PRAGMA integrity_check").fetchall()
        return tuple(str(row[0]) for row in rows)

    def backup(self,destination:Path|None=None)->dict[str,str|int]:
        if destination is None:
            stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            destination=self.path.with_name(f"{self.path.stem}.backup-{stamp}{self.path.suffix}")
        destination=destination.resolve()
        if destination==self.path: raise ValueError("backup destination must differ from source")
        destination.parent.mkdir(parents=True,exist_ok=True)
        source=sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro",uri=True,timeout=5)
        target=sqlite3.connect(destination,timeout=5)
        try:
            source.backup(target)
        finally:
            target.close(); source.close()
        return {"source":str(self.path),"destination":str(destination),"bytes":destination.stat().st_size}

    def wal_checkpoint(self,mode:str="PASSIVE")->tuple[int,int,int]:
        mode=mode.upper()
        if mode not in ("PASSIVE","FULL","RESTART","TRUNCATE"): raise ValueError("invalid WAL checkpoint mode")
        with sqlite3.connect(self.path,timeout=5) as db:
            row=db.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
        if row is None: raise RuntimeError("WAL checkpoint returned no result")
        return tuple(int(x) for x in row)

    def vacuum(self)->dict[str,bool]:
        db=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try: db.execute("VACUUM")
        finally: db.close()
        return {"vacuumed":True}

    def _connect_ro(self):
        uri=f"file:{self.path.as_posix()}?mode=ro"
        return sqlite3.connect(uri,uri=True,timeout=5)
