from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import shutil
import sqlite3


@dataclass(frozen=True,slots=True)
class RecoverySnapshot:
    source:Path
    snapshot:Path
    sha256:str
    bytes:int
    created_at:datetime
    sqlite_integrity:tuple[str,...]

    @property
    def verified(self)->bool:
        return (
            self.bytes>=0
            and len(self.sha256)==64
            and self.sqlite_integrity==("ok",)
        )


class RecoverySnapshotManager:
    """Create and verify recovery material before CLEAN mutates state."""

    def __init__(self,recovery_root:Path)->None:
        if not isinstance(recovery_root,Path):
            raise TypeError("recovery_root must be a Path")
        self.root=recovery_root
        self.root.mkdir(parents=True,exist_ok=True)

    @staticmethod
    def _digest(path:Path)->str:
        h=sha256()
        with path.open("rb") as fh:
            for block in iter(lambda:fh.read(1024*1024),b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _integrity(path:Path)->tuple[str,...]:
        uri=f"file:{path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri,uri=True,timeout=10) as db:
            rows=db.execute("PRAGMA integrity_check").fetchall()
        return tuple(str(row[0]) for row in rows)

    def snapshot_sqlite(
        self,
        source:Path,
        *,
        label:str="state",
        now:datetime|None=None,
    )->RecoverySnapshot:
        if not isinstance(source,Path) or not source.is_file():
            raise FileNotFoundError("existing SQLite source required")
        if not isinstance(label,str) or not label.strip():
            raise ValueError("label must be nonempty")
        moment=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        stamp=moment.strftime("%Y%m%dT%H%M%SZ")
        target=self.root/f"{label}-{stamp}.sqlite"
        if target.exists():
            raise FileExistsError("recovery snapshot already exists")
        src=sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro",uri=True,timeout=10)
        dst=sqlite3.connect(target,timeout=10)
        try:
            src.backup(dst)
        finally:
            dst.close(); src.close()
        result=RecoverySnapshot(
            source=source.resolve(),
            snapshot=target.resolve(),
            sha256=self._digest(target),
            bytes=target.stat().st_size,
            created_at=moment,
            sqlite_integrity=self._integrity(target),
        )
        if not result.verified:
            target.unlink(missing_ok=True)
            raise RuntimeError("recovery snapshot failed verification")
        manifest=target.with_suffix(target.suffix+".json")
        manifest.write_text(json.dumps({
            "source":str(result.source),
            "snapshot":str(result.snapshot),
            "sha256":result.sha256,
            "bytes":result.bytes,
            "created_at":result.created_at.isoformat(),
            "sqlite_integrity":list(result.sqlite_integrity),
        },sort_keys=True,indent=2),encoding="utf-8")
        return result

    def verify(self,snapshot:RecoverySnapshot)->bool:
        if not isinstance(snapshot,RecoverySnapshot):
            raise TypeError("snapshot must be RecoverySnapshot")
        if not snapshot.snapshot.is_file():
            return False
        return (
            self._digest(snapshot.snapshot)==snapshot.sha256
            and snapshot.snapshot.stat().st_size==snapshot.bytes
            and self._integrity(snapshot.snapshot)==("ok",)
        )
