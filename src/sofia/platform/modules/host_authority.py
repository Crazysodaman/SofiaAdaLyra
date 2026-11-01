"""Exact remote authority for a Core-free MODULE_HOST.

Global authority never leaves the approved Core.  A module host therefore
never mints lifecycle authority itself.  ``LocalModuleAuthority`` holds only
Core-issued approval receipts that were explicitly imported for this exact
host, enforces single-use consumption, expiry, and remote revocation, and
mirrors the owner's operator STOP so safety-reducing operations stay
available when the host is cut off.

It reuses SAFE's reviewed one-time approval fingerprint and append-only audit
chain; it does not implement a second grant system.  Approvals can only enter
through ``import_core_approval``, and never while the host is offline:
offline operation restriction emerges because only previously imported,
unexpired, unrevoked receipts remain consumable.
"""
from __future__ import annotations

from contextlib import closing, nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopState
from sofia.platform.state.local_store import PlatformLocalStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_module_host_approval(
    approval_id TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    revoked_at TEXT,
    core_identity TEXT NOT NULL,
    host_identity TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS platform_module_host_stop(
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    reason TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class ImportedApprovalBinding:
    """Exact provenance of one Core-issued approval receipt."""

    core_identity: str
    host_identity: str
    imported_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.core_identity, str) or not self.core_identity.strip():
            raise ValueError("core_identity required")
        if not isinstance(self.host_identity, str) or not self.host_identity.strip():
            raise ValueError("host_identity required")
        if not isinstance(self.imported_at, datetime) or (
            self.imported_at.tzinfo is None or self.imported_at.utcoffset() is None
        ):
            raise ValueError("imported_at must be timezone-aware")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class LocalModuleAuthority:
    """Host-local, single-use ledger of remote Core-issued approvals."""

    def __init__(self, storage: PlatformLocalStore) -> None:
        if not isinstance(storage, PlatformLocalStore):
            raise TypeError("module host authority requires a PlatformLocalStore")
        self.store = storage
        self.audit = AuditChain(storage)
        with closing(self._connect()) as db, db:
            db.execute("PRAGMA busy_timeout=10000")
            db.execute("BEGIN IMMEDIATE")
            existed = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='platform_module_host_stop'"
            ).fetchone() is not None
            db.executescript(SCHEMA)
            row = db.execute(
                "SELECT 1 FROM platform_module_host_stop WHERE singleton=1"
            ).fetchone()
            if row is None:
                if existed:
                    raise RuntimeError(
                        "module host stop state missing after initialization; "
                        "local recovery and owner review required"
                    )
                db.execute(
                    "INSERT INTO platform_module_host_stop VALUES(1,0,?,?,?)",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        "system:bootstrap",
                        "initial inactive module host stop",
                    ),
                )
    def _connect(self) -> sqlite3.Connection:
        db = self.store.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    # ---- Core binding ------------------------------------------------------

    def _binding(self) -> ImportedApprovalBinding:
        binding = self.store.binding
        core = binding.core_identity
        if core is None:
            raise PermissionError(
                "module host has no bound remote Core authority; approvals "
                "cannot be imported or consumed"
            )
        return ImportedApprovalBinding(
            core_identity=core,
            host_identity=binding.host_identity,
            imported_at=binding.created_at,
        )

    def _check_import_binding(
        self, binding: ImportedApprovalBinding,
        *, host_identity: str, core_identity: str,
    ) -> None:
        if host_identity != binding.host_identity:
            raise PermissionError(
                "approval was not issued for this exact host identity"
            )
        if core_identity != binding.core_identity:
            raise PermissionError(
                "approval was not issued by the bound remote Core"
            )

    # ---- approval import ---------------------------------------------------

    def import_core_approval(
        self, approval: ExecutionApproval, *, binding: ImportedApprovalBinding,
    ) -> None:
        """Record one Core-issued receipt for this exact host binding.

        Import is idempotent and immutable: an already recorded approval may be
        replayed only as an exact document duplicate, and a consumed or
        imported receipt is never rewritten, so Core Link reconciliation can
        replay its delivery log safely.
        """
        if not isinstance(approval, ExecutionApproval):
            raise TypeError("approval must be an ExecutionApproval")
        if not isinstance(binding, ImportedApprovalBinding):
            raise TypeError("binding must be an ImportedApprovalBinding")
        provenance = self._binding()
        self._check_import_binding(
            provenance, host_identity=binding.host_identity,
            core_identity=binding.core_identity,
        )
        core_identity = provenance.core_identity
        host_identity = provenance.host_identity
        moment = _utc(binding.imported_at)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT capability,request_fingerprint,approved_by,approved_at,"
                "expires_at,consumed_at,revoked_at,core_identity,host_identity,"
                "imported_at FROM platform_module_host_approval WHERE approval_id=?",
                (approval.approval_id,),
            ).fetchone()
            document = (
                approval.capability, approval.request_fingerprint,
                approval.approved_by,
                _utc(approval.approved_at).isoformat(),
                _utc(approval.expires_at).isoformat(),
            )
            if existing is not None:
                stored = (
                    str(existing["capability"]),
                    str(existing["request_fingerprint"]),
                    str(existing["approved_by"]),
                    str(existing["approved_at"]),
                    str(existing["expires_at"]),
                )
                if stored != document or existing["host_identity"] != host_identity or (
                    existing["core_identity"] != core_identity
                ):
                    raise PermissionError(
                        "approval import conflicts with the recorded receipt"
                    )
                return
            db.execute(
                "INSERT INTO platform_module_host_approval "
                "(approval_id,capability,request_fingerprint,approved_by,"
                "approved_at,expires_at,consumed_at,revoked_at,core_identity,"
                "host_identity,imported_at) VALUES(?,?,?,?,?,?,NULL,NULL,?,?,?)",
                (approval.approval_id, *document, core_identity, host_identity,
                 moment.isoformat()),
            )
            db.commit()

    def revoke_core_approval(self, approval_id: str, *, binding: ImportedApprovalBinding) -> None:
        """Record remote revocation without ever resurrecting a receipt.

        Revocation of an approval this host never received is an audited
        no-op so Core Link reconciliation stays idempotent; a consumed
        receipt is already spent and cannot become dangerous again.
        """
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("approval_id required")
        provenance = self._binding()
        self._check_import_binding(
            provenance, host_identity=binding.host_identity,
            core_identity=binding.core_identity,
        )
        core_identity = provenance.core_identity
        moment = _utc(binding.imported_at).isoformat()
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT consumed_at,revoked_at,core_identity FROM "
                "platform_module_host_approval WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None or row["consumed_at"] is not None or (
                row["revoked_at"] is not None
            ) or row["core_identity"] != core_identity:
                db.commit()
                self.audit.append(
                    actor_id="platform:core-link",
                    event_type="modulehost.approval.revoke.noop",
                    payload={
                        "approval_id": approval_id,
                        "recorded": row is not None,
                        "revoked": bool(row is not None and row["revoked_at"]),
                    },
                    occurred_at=_utc(binding.imported_at),
                    event_id=f"modulehost-approval-revoke:{approval_id}",
                )
                return
            changed = db.execute(
                "UPDATE platform_module_host_approval SET revoked_at=? "
                "WHERE approval_id=? AND consumed_at IS NULL AND revoked_at IS NULL",
                (moment, approval_id),
            )
            if changed.rowcount != 1:
                raise PermissionError(
                    "module host approval revocation compare-and-swap failed"
                )
            self.audit.append_in_transaction(
                db,
                actor_id="platform:core-link",
                event_type="modulehost.approval.revoked",
                payload={"approval_id": approval_id},
                occurred_at=_utc(binding.imported_at),
                event_id=f"modulehost-approval-revoked:{approval_id}",
            )
            db.commit()

    # ---- exact consumption -------------------------------------------------

    def consume(
        self,
        *,
        approval_id: str,
        capability: str,
        parameters: dict,
        now: datetime,
        _transaction_db: sqlite3.Connection | None = None,
    ) -> ExecutionApproval:
        """Consume one exact host-bound remote approval, at most once.

        The parameters fingerprint, expiry window, approval identity, and
        status rules are the reviewed SAFE contract; the approval is foreign
        and revocable, so a locally recorded revocation also fail-closes.
        """
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise PermissionError("side-effect capability requires approval_id")
        if not isinstance(capability, str) or not capability.strip():
            raise ValueError("capability must be nonempty")
        if not isinstance(now, datetime) or now.tzinfo is None or (
            now.utcoffset() is None
        ):
            raise ValueError("now must be timezone-aware")
        moment = _utc(now)
        expected = execution_fingerprint(capability, parameters)
        provenance = self._binding()
        own_connection = _transaction_db is None
        context = (
            closing(self._connect()) if own_connection
            else nullcontext(_transaction_db)
        )
        with context as db:
            if not own_connection and not db.in_transaction:
                raise RuntimeError(
                    "shared module host approval consumption requires an open transaction"
                )
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            if own_connection:
                db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT capability,request_fingerprint,approved_by,approved_at,"
                "expires_at,consumed_at,revoked_at,core_identity,host_identity "
                "FROM platform_module_host_approval WHERE approval_id=?",
                (approval_id,),
            ).fetchone()
            if row is None:
                raise PermissionError("module host approval does not exist")
            if row["consumed_at"] is not None:
                raise PermissionError("module host approval was already consumed")
            if row["revoked_at"] is not None:
                raise PermissionError("module host approval was remotely revoked")
            if (
                row["host_identity"] != provenance.host_identity
                or row["core_identity"] != provenance.core_identity
            ):
                raise PermissionError(
                    "module host approval binding is stale"
                )
            approval = ExecutionApproval(
                approval_id=approval_id,
                capability=str(row["capability"]),
                request_fingerprint=str(row["request_fingerprint"]),
                approved_by=str(row["approved_by"]),
                approved_at=datetime.fromisoformat(str(row["approved_at"])),
                expires_at=datetime.fromisoformat(str(row["expires_at"])),
            )
            if moment < approval.approved_at.astimezone(timezone.utc):
                raise PermissionError("module host approval is not active yet")
            if _utc(moment) >= _utc(approval.expires_at):
                raise PermissionError("module host approval expired")
            if approval.approved_by != "Sparks":
                raise PermissionError(
                    "module host approval was not granted by the owner"
                )
            if approval.capability != capability:
                raise PermissionError(
                    "module host approval is for another capability"
                )
            if approval.request_fingerprint != expected:
                raise PermissionError(
                    "module host approval parameters do not match"
                )
            changed = db.execute(
                "UPDATE platform_module_host_approval SET consumed_at=? "
                "WHERE approval_id=? AND consumed_at IS NULL AND revoked_at IS NULL",
                (moment.isoformat(), approval_id),
            )
            if changed.rowcount != 1:
                raise PermissionError(
                    "module host approval could not be consumed"
                )
            self.audit.append_in_transaction(
                db,
                actor_id=approval.approved_by,
                event_type="modulehost.approval.consumed",
                payload={
                    "approval_id": approval.approval_id,
                    "capability": approval.capability,
                    "request_fingerprint": approval.request_fingerprint,
                    "core_identity": provenance.core_identity,
                },
                occurred_at=moment,
                event_id=f"modulehost-approval-consumed:{approval.approval_id}",
            )
            if own_connection:
                db.commit()
            return approval

    # ---- operator stop mirror ---------------------------------------------

    def mirror_operator_stop(
        self, *, active: bool, updated_by: str, reason: str, at: datetime,
    ) -> OperatorStopState:
        """Record the owner's operator STOP/RESUME as mirrored from Core.

        This is a safety mirror, not a local grant authority: it can only
        *deny* host operations.  Only the owner identity may write it, so an
        arbitrary module cannot silence the stop.
        """
        if not isinstance(active, bool):
            raise TypeError("active must be boolean")
        if updated_by != "Sparks":
            raise PermissionError(
                "module host stop authority is explicitly the owner"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason must be nonempty")
        moment = _utc(at)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT active FROM platform_module_host_stop WHERE singleton=1"
            ).fetchone()
            if previous is None:
                raise RuntimeError("module host stop row missing")
            changed = db.execute(
                "UPDATE platform_module_host_stop SET active=?,updated_at=?,"
                "updated_by=?,reason=? WHERE singleton=1",
                (1 if active else 0, moment.isoformat(), updated_by, reason.strip()),
            )
            if changed.rowcount != 1:
                raise RuntimeError("module host stop update failed")
            self.audit.append_in_transaction(
                db,
                actor_id=updated_by,
                event_type=(
                    "modulehost.stop.activated" if active
                    else "modulehost.stop.cleared"
                ),
                payload={
                    "previously_active": bool(previous[0]),
                    "active": active,
                    "reason": reason.strip(),
                },
                occurred_at=moment,
                event_id=f"modulehost-stop:{active}-{moment.isoformat()}",
            )
        return self.current()

    def current(self) -> OperatorStopState:
        with closing(self._connect()) as db:
            row = db.execute(
                """SELECT active,updated_at,updated_by,reason
                FROM platform_module_host_stop WHERE singleton=1"""
            ).fetchone()
        if row is None:
            raise RuntimeError("module host stop state is missing")
        return OperatorStopState(
            active=bool(row["active"]),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
            updated_by=str(row["updated_by"]),
            reason=str(row["reason"]),
        )
