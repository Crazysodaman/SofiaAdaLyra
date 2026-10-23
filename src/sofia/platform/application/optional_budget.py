"""Canonical finite quota for optional autonomy, never foreground conversation.

The coordinator already serializes background work. Reservations extend that
same SQLite transaction, so crashes, multiple workers and concurrency cannot
double-spend one daily optional budget. Units are conservative reservations,
NOT fabricated measurements of CPU, GPU, LLM tokens or VRAM.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from contextlib import closing
import sqlite3
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

@dataclass(frozen=True,slots=True)
class OptionalBudgetLimits:
    # Owner-selected V18 background admission defaults. Estimates, not metered usage.
    tokens:int=200_000
    cpu_ms:int=10_800_000
    gpu_ms:int=3_600_000
    storage_bytes:int=536_870_912
    occupied_latency_ms:int=7_200_000

    def __post_init__(self):
        for name in ("tokens","cpu_ms","gpu_ms","storage_bytes","occupied_latency_ms"):
            val=getattr(self,name)
            if type(val) is not int or not 0<=val<=1_000_000_000_000:
                raise ValueError("finite nonnegative resource limit: "+name)

@dataclass(frozen=True,slots=True)
class OptionalWorkReservation:
    tokens:int
    cpu_ms:int
    gpu_ms:int
    storage_bytes:int
    occupied_latency_ms:int

    def __post_init__(self):
        if any(type(v) is not int or v<0 for v in (
            self.tokens,self.cpu_ms,self.gpu_ms,
            self.storage_bytes,self.occupied_latency_ms,
        )):
            raise ValueError("nonnegative estimated reservations required")

def reserve_profile(task_kind:str)->OptionalWorkReservation:
    """Validated worst-case credits, not measured device usage."""
    if not isinstance(task_kind,str) or not task_kind.strip() or len(task_kind)>120:
        raise ValueError("bounded background work name required")
    name=task_kind.lower()
    if name in {"neuro_refresh","presence_refresh","act_delivery"}:
        return OptionalWorkReservation(0,500,0,65_536,5_000)
    if name.startswith(("fleet","backup","system","ops_","maintenance")):
        return OptionalWorkReservation(0,2000,0,131_072,30_000)
    if name in {"reflection","idle_reflection","wardrobe_review"} or (
        name.startswith(("life","goal","creative","model_","voice","vision"))
    ):
        return OptionalWorkReservation(4096,6000,15_000,1_048_576,60_000)
    # Unknown callback kinds are NOT free. Either explicitly classify them
    # as deterministic or conservatively reserve the model-capable tier.
    return OptionalWorkReservation(4096,6000,15_000,1_048_576,60_000)

class OptionalAutonomyBudget:
    """One explicit daily reservation ledger inside canonical sofia.db."""

    FIELDS=("tokens","cpu_ms","gpu_ms","storage_bytes","occupied_latency_ms")

    def __init__(self,state_path:Path):
        if not isinstance(state_path,Path):
            raise TypeError("canonical state path required")
        self.guard=CanonicalSQLiteGuard(state_path)
        with closing(self.guard.connect(timeout=10)) as db,db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS application_optional_budget_settings("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "tokens INTEGER NOT NULL,cpu_ms INTEGER NOT NULL,"
                "gpu_ms INTEGER NOT NULL,storage_bytes INTEGER NOT NULL,"
                "occupied_latency_ms INTEGER NOT NULL,revision INTEGER NOT NULL)"
            )
            defaults=OptionalBudgetLimits()
            db.execute(
                "INSERT OR IGNORE INTO application_optional_budget_settings VALUES"
                "(1,?,?,?,?,?,0)",
                tuple(getattr(defaults,name) for name in self.FIELDS),
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS application_optional_budget_claim("
                "claim_id TEXT PRIMARY KEY,day_utc TEXT NOT NULL,"
                "task_kind TEXT NOT NULL,tokens INTEGER NOT NULL,"
                "cpu_ms INTEGER NOT NULL,gpu_ms INTEGER NOT NULL,"
                "storage_bytes INTEGER NOT NULL,"
                "occupied_latency_ms INTEGER NOT NULL,"
                "status TEXT NOT NULL CHECK(status IN ('working','done','failed')),"
                "finished_at TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS application_optional_budget_claim_day "
                "ON application_optional_budget_claim(day_utc)"
            )

    @classmethod
    def _limits(cls,db:sqlite3.Connection)->tuple[OptionalBudgetLimits,int]:
        values=db.execute(
            "SELECT tokens,cpu_ms,gpu_ms,storage_bytes,occupied_latency_ms,revision "
            "FROM application_optional_budget_settings WHERE singleton=1"
        ).fetchone()
        if values is None:
            raise RuntimeError("canonical optional budget configuration missing")
        return OptionalBudgetLimits(*values[:5]),values[5]

    def limits(self)->tuple[OptionalBudgetLimits,int]:
        with closing(self.guard.connect(timeout=10)) as db:
            return self._limits(db)

    def update_owner_limits(self,limits:OptionalBudgetLimits,*,expected_revision:int):
        """Called ONLY by interactive owner Settings, never a model tool."""
        if not isinstance(limits,OptionalBudgetLimits):
            raise TypeError("owner budget settings required")
        if type(expected_revision) is not int or expected_revision<0:
            raise ValueError("valid settings revision required")
        with closing(self.guard.connect(timeout=10)) as db,db:
            db.execute("BEGIN IMMEDIATE")
            changed=db.execute(
                "UPDATE application_optional_budget_settings SET "
                "tokens=?,cpu_ms=?,gpu_ms=?,storage_bytes=?,"
                "occupied_latency_ms=?,revision=revision+1 "
                "WHERE singleton=1 AND revision=?",
                tuple(getattr(limits,name) for name in self.FIELDS)
                +(expected_revision,),
            )
            if changed.rowcount!=1:
                raise PermissionError("budget changed since owner review")

    def reserve_in_transaction(self,db:sqlite3.Connection,*,claim_id:str,
                               task_kind:str,now:datetime)->bool:
        if not isinstance(db,sqlite3.Connection) or not db.in_transaction:
            raise RuntimeError(
                "optional reservation requires existing canonical write transaction"
            )
        if not isinstance(claim_id,str) or not claim_id.strip() or len(claim_id)>160:
            raise ValueError("bounded optional reservation identity required")
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware budget accounting time required")
        profile=reserve_profile(task_kind)
        limits,_=self._limits(db)
        day=now.astimezone(timezone.utc).date().isoformat()
        used=db.execute(
            "SELECT COALESCE(SUM(tokens),0),COALESCE(SUM(cpu_ms),0),"
            "COALESCE(SUM(gpu_ms),0),COALESCE(SUM(storage_bytes),0),"
            "COALESCE(SUM(occupied_latency_ms),0) "
            "FROM application_optional_budget_claim WHERE day_utc=?",
            (day,),
        ).fetchone()
        if any(
            spent+getattr(profile,name)>getattr(limits,name)
            for name,spent in zip(self.FIELDS,used)
        ):
            return False
        db.execute(
            "INSERT INTO application_optional_budget_claim VALUES("
            "?,?,?,?,?,?,?,?,'working',NULL)",
            (claim_id,day,task_kind,*
             (getattr(profile,name) for name in self.FIELDS)),
        )
        return True

    def settle_in_transaction(self,db:sqlite3.Connection,*,claim_id:str,
                              now:datetime,failed:bool)->None:
        if not isinstance(db,sqlite3.Connection) or not db.in_transaction:
            raise RuntimeError(
                "optional settlement requires existing canonical write transaction"
            )
        if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware budget settlement time required")
        if type(failed) is not bool:
            raise TypeError("reservation failure status must be bool")
        result=db.execute(
            "UPDATE application_optional_budget_claim SET status=?,finished_at=? "
            "WHERE claim_id=? AND status='working'",
            ("failed" if failed else "done",
             now.astimezone(timezone.utc).isoformat(),claim_id),
        )
        if result.rowcount!=1:
            raise RuntimeError("optional reservation missing or already settled")

    def report(self,*,now:datetime)->dict:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("aware report time required")
        with closing(self.guard.connect(timeout=10)) as db:
            limits,revision=self._limits(db)
            rows=db.execute(
                "SELECT tokens,cpu_ms,gpu_ms,storage_bytes,occupied_latency_ms,"
                "status FROM application_optional_budget_claim WHERE day_utc=?",
                (now.astimezone(timezone.utc).date().isoformat(),),
            ).fetchall()
        totals={name:sum(row[i] for row in rows) for i,name in enumerate(self.FIELDS)}
        return {
            "day_utc":now.astimezone(timezone.utc).date().isoformat(),
            "revision":revision,
            "limits":{name:getattr(limits,name) for name in self.FIELDS},
            "reserved":totals,
            "attempts":len(rows),
            "unfinished":sum(row[-1]=="working" for row in rows),
            "note":"Reserved upper-bound credits, NOT measured CPU/GPU/tokens/VRAM or job completion.",
            "can_preempt_foreground":False,
        }
