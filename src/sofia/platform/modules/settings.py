"""Canonical settings state for exact, signed module packages.

The signed manifest describes values but grants no write or execution
authority.  This service stores settings in the existing canonical state,
fences every mutation to the current lifecycle/package revision, and invokes
only handlers registered by trusted Platform construction.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from typing import Callable, Mapping

from sofia.platform.config.settings_authority import SettingsApplyState
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.sdk.module_settings import (
    ModuleSettingApplyClass,
    ModuleSettingsContract,
    module_settings_contract_from_document,
    module_settings_contract_to_document,
)

from .lifecycle import ModuleLifecycle


@dataclass(frozen=True, slots=True)
class ModuleSettingsAuthorization:
    module_id: str
    package_digest: str
    lifecycle_revision: int
    expected_settings_revision: int
    principal_id: str
    audience_id: str
    approval_ref: str
    changed_fields: tuple[str, ...]
    occurred_at: datetime

    @property
    def capability(self) -> str:
        return "module.settings.update"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "module_id": self.module_id,
            "package_digest": self.package_digest,
            "lifecycle_revision": self.lifecycle_revision,
            "expected_settings_revision": self.expected_settings_revision,
            "principal_id": self.principal_id,
            "audience_id": self.audience_id,
            "changed_fields": list(self.changed_fields),
        }


@dataclass(frozen=True, slots=True)
class ModuleSettingsReceipt:
    module_id: str
    package_digest: str
    revision: int
    effective_revision: int
    apply_state: SettingsApplyState
    changed_fields: tuple[str, ...]
    apply_classes: tuple[str, ...]
    error: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "module_id": self.module_id,
            "package_digest": self.package_digest,
            "revision": self.revision,
            "effective_revision": self.effective_revision,
            "apply_state": self.apply_state.value,
            "changed_fields": list(self.changed_fields),
            "apply_classes": list(self.apply_classes),
            "error": self.error,
        }


ModuleSettingsAuthorizer = Callable[
    [ModuleSettingsAuthorization, sqlite3.Connection], bool
]
ModuleSettingsApplyHandler = Callable[
    [str, str, Mapping[str, object], tuple[str, ...]], None
]


class ModuleSettingsService:
    """Revisioned module settings in the canonical Platform database."""

    def __init__(self, state_path, *, authorizer: ModuleSettingsAuthorizer) -> None:
        if not callable(authorizer):
            raise TypeError("module settings authorizer must be callable")
        self._guard = CanonicalSQLiteGuard(state_path)
        self._authorizer = authorizer
        self._handlers: dict[tuple[str, str], ModuleSettingsApplyHandler] = {}
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_module_settings_state(
                    module_id TEXT PRIMARY KEY,
                    package_digest TEXT NOT NULL,
                    contract_digest TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    effective_revision INTEGER NOT NULL,
                    values_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS platform_module_settings_request(
                    module_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(module_id,client_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS platform_module_settings_event(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    module_id TEXT NOT NULL,
                    package_digest TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    client_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    changed_fields_json TEXT NOT NULL,
                    apply_state TEXT NOT NULL,
                    effective_revision INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(module_id,revision)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = self._guard.connect(timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )

    def register_apply_handler(
        self, *, module_id: str, package_digest: str,
        handler: ModuleSettingsApplyHandler,
    ) -> None:
        """Register one reviewed handler for one immutable package identity."""
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("module_id required")
        if (
            not isinstance(package_digest, str) or len(package_digest) != 64
            or any(character not in "0123456789abcdef" for character in package_digest)
        ):
            raise ValueError("exact lowercase package digest required")
        if not callable(handler):
            raise TypeError("module settings handler must be callable")
        key = (module_id, package_digest)
        existing = self._handlers.get(key)
        if existing is not None and existing is not handler:
            raise RuntimeError("module settings handler identity conflict")
        self._handlers[key] = handler

    def _policy_locked(
        self, db: sqlite3.Connection, module_id: str,
    ) -> tuple[str, int, ModuleLifecycle, ModuleSettingsContract, str]:
        row = db.execute(
            "SELECT l.package_digest,l.revision,l.lifecycle,p.package_digest AS "
            "projection_digest,p.manifest_json FROM platform_module_lifecycle l "
            "JOIN platform_module_manifest_projection p ON p.module_id=l.module_id "
            "WHERE l.module_id=?", (module_id,),
        ).fetchone()
        if row is None:
            raise LookupError("module settings require an admitted signed package")
        package_digest = str(row["package_digest"])
        if row["projection_digest"] != package_digest:
            raise RuntimeError("module settings manifest identity mismatch")
        manifest_json = str(row["manifest_json"])
        if sha256(manifest_json.encode("utf-8")).hexdigest() != package_digest:
            raise RuntimeError("module settings manifest projection was altered")
        manifest = json.loads(manifest_json)
        raw_contract = manifest.get("settings_contract")
        if raw_contract is None:
            raise LookupError("signed module has no settings contract")
        contract = module_settings_contract_from_document(raw_contract)
        contract_json = self._json(module_settings_contract_to_document(contract))
        contract_digest = sha256(contract_json.encode("utf-8")).hexdigest()
        lifecycle = ModuleLifecycle(row["lifecycle"])
        if lifecycle in {ModuleLifecycle.DISCOVERED, ModuleLifecycle.REMOVED}:
            raise PermissionError("module lifecycle does not permit settings")
        return package_digest, int(row["revision"]), lifecycle, contract, contract_digest

    def _state_locked(
        self, db: sqlite3.Connection, *, module_id: str,
        package_digest: str, contract_digest: str, now: datetime,
    ) -> sqlite3.Row:
        row = db.execute(
            "SELECT * FROM platform_module_settings_state WHERE module_id=?",
            (module_id,),
        ).fetchone()
        if row is None:
            db.execute(
                "INSERT INTO platform_module_settings_state VALUES(?,?,?,?,?,?,?)",
                (module_id, package_digest, contract_digest, 0, 0, "{}",
                 now.isoformat()),
            )
            row = db.execute(
                "SELECT * FROM platform_module_settings_state WHERE module_id=?",
                (module_id,),
            ).fetchone()
        if (
            row["package_digest"] != package_digest
            or row["contract_digest"] != contract_digest
        ):
            raise RuntimeError(
                "module package changed; reviewed settings migration is required"
            )
        return row

    def snapshot(self, *, module_id: str) -> dict[str, object]:
        moment = datetime.now(timezone.utc)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            package, lifecycle_revision, lifecycle, contract, digest = (
                self._policy_locked(db, module_id)
            )
            state = self._state_locked(
                db, module_id=module_id, package_digest=package,
                contract_digest=digest, now=moment,
            )
            db.commit()
        values = contract.validate_partial(json.loads(state["values_json"]))
        secret_fields = {
            field.field_id for field in contract.fields if field.secret_reference
        }
        return {
            "module_id": module_id,
            "package_digest": package,
            "lifecycle": lifecycle.value,
            "lifecycle_revision": lifecycle_revision,
            "revision": int(state["revision"]),
            "effective_revision": int(state["effective_revision"]),
            "values": {
                key: "<protected-secret-reference>" if key in secret_fields else value
                for key, value in values.items()
            },
            "contract": module_settings_contract_to_document(contract),
        }

    def catalog(self) -> tuple[dict[str, object], ...]:
        """Return exact signed contracts without initializing module values."""
        with closing(self._connect()) as db:
            module_ids = tuple(
                str(row[0]) for row in db.execute(
                    "SELECT module_id FROM platform_module_lifecycle "
                    "WHERE lifecycle NOT IN ('discovered','removed') "
                    "ORDER BY module_id"
                )
            )
            result = []
            for module_id in module_ids:
                try:
                    package, lifecycle_revision, lifecycle, contract, _ = (
                        self._policy_locked(db, module_id)
                    )
                except LookupError:
                    continue
                state = db.execute(
                    "SELECT package_digest,revision,effective_revision FROM "
                    "platform_module_settings_state WHERE module_id=?",
                    (module_id,),
                ).fetchone()
                package_matches = state is None or state["package_digest"] == package
                result.append({
                    "module_id": module_id,
                    "package_digest": package,
                    "lifecycle": lifecycle.value,
                    "lifecycle_revision": lifecycle_revision,
                    "revision": 0 if state is None else int(state["revision"]),
                    "effective_revision": (
                        0 if state is None else int(state["effective_revision"])
                    ),
                    "settings_identity": (
                        "current" if package_matches else "migration_required"
                    ),
                    "contract": module_settings_contract_to_document(contract),
                })
        return tuple(result)

    def update(
        self, *, module_id: str, expected_package_digest: str,
        expected_lifecycle_revision: int, expected_revision: int,
        client_id: str, principal_id: str, audience_id: str,
        approval_ref: str, idempotency_key: str,
        changes: Mapping[str, object], now: datetime,
    ) -> ModuleSettingsReceipt:
        if not isinstance(changes, Mapping) or not changes or len(changes) > 64:
            raise ValueError("module settings changes must be a bounded nonempty object")
        if any(not isinstance(key, str) for key in changes):
            raise ValueError("module settings field names must be strings")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected settings revision must be nonnegative")
        if type(expected_lifecycle_revision) is not int or expected_lifecycle_revision < 1:
            raise ValueError("expected lifecycle revision must be positive")
        for label, value in (
            ("module_id", module_id), ("expected_package_digest", expected_package_digest),
            ("client_id", client_id), ("principal_id", principal_id),
            ("audience_id", audience_id), ("approval_ref", approval_ref),
            ("idempotency_key", idempotency_key),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("module settings timestamp must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        fields = tuple(sorted(changes))
        request_document = {
            "module_id": module_id,
            "expected_package_digest": expected_package_digest,
            "expected_lifecycle_revision": expected_lifecycle_revision,
            "expected_revision": expected_revision,
            "principal_id": principal_id,
            "audience_id": audience_id,
            "changes": dict(changes),
        }
        request_digest = sha256(
            self._json(request_document).encode("utf-8")
        ).hexdigest()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT request_digest,receipt_json FROM "
                "platform_module_settings_request WHERE module_id=? AND client_id=? "
                "AND idempotency_key=?", (module_id, client_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["request_digest"] != request_digest:
                    raise RuntimeError("module settings idempotency payload conflict")
                db.commit()
                return self._receipt(json.loads(prior["receipt_json"]))
            package, lifecycle_revision, lifecycle, contract, contract_digest = (
                self._policy_locked(db, module_id)
            )
            if package != expected_package_digest:
                raise RuntimeError("module settings package revision conflict")
            if lifecycle_revision != expected_lifecycle_revision:
                raise RuntimeError("module settings lifecycle revision conflict")
            state = self._state_locked(
                db, module_id=module_id, package_digest=package,
                contract_digest=contract_digest, now=moment,
            )
            if int(state["revision"]) != expected_revision:
                raise RuntimeError("module settings revision conflict")
            current = json.loads(state["values_json"])
            current.update(dict(changes))
            candidate = contract.validate(current)
            classes = tuple(sorted({
                field.apply_class.value for field in contract.fields
                if field.field_id in fields
            }))
            revision = expected_revision + 1
            apply_state = self._initial_apply_state(classes)
            authorization = ModuleSettingsAuthorization(
                module_id, expected_package_digest, expected_lifecycle_revision,
                expected_revision, principal_id, audience_id, approval_ref,
                fields, moment,
            )
            if not self._authorizer(authorization, db):
                raise PermissionError("module settings update not authorized")
            receipt = ModuleSettingsReceipt(
                module_id, package, revision, int(state["effective_revision"]),
                apply_state, fields, classes,
            )
            updated = db.execute(
                "UPDATE platform_module_settings_state SET revision=?,values_json=?,"
                "updated_at=? WHERE module_id=? AND revision=?",
                (revision, self._json(candidate), moment.isoformat(), module_id,
                 expected_revision),
            )
            if updated.rowcount != 1:
                raise RuntimeError("module settings compare-and-swap failed")
            db.execute(
                "INSERT INTO platform_module_settings_event VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)",
                (module_id, package, revision, client_id, principal_id, audience_id,
                 self._json(list(fields)), apply_state.value,
                 receipt.effective_revision, None, moment.isoformat()),
            )
            db.execute(
                "INSERT INTO platform_module_settings_request VALUES(?,?,?,?,?,?)",
                (module_id, client_id, idempotency_key, request_digest,
                 self._json(receipt.to_payload()), moment.isoformat()),
            )
            db.commit()

        if classes == (ModuleSettingApplyClass.LIVE.value,):
            receipt = self._apply_live(
                receipt=receipt, lifecycle=lifecycle, values=candidate,
            )
            self._settle(client_id, idempotency_key, receipt)
        return receipt

    @staticmethod
    def _initial_apply_state(classes: tuple[str, ...]) -> SettingsApplyState:
        if ModuleSettingApplyClass.COMPONENT_RESTART.value in classes:
            return SettingsApplyState.PENDING_COMPONENT_RESTART
        if ModuleSettingApplyClass.NEXT_OPERATION.value in classes:
            return SettingsApplyState.PENDING_NEXT_OPERATION
        return SettingsApplyState.UNKNOWN

    def _apply_live(
        self, *, receipt: ModuleSettingsReceipt, lifecycle: ModuleLifecycle,
        values: Mapping[str, object],
    ) -> ModuleSettingsReceipt:
        if lifecycle is not ModuleLifecycle.ACTIVE:
            return ModuleSettingsReceipt(
                receipt.module_id, receipt.package_digest, receipt.revision,
                receipt.effective_revision, SettingsApplyState.UNKNOWN,
                receipt.changed_fields, receipt.apply_classes,
                "module is not active",
            )
        if not self._is_active_package(receipt.module_id, receipt.package_digest):
            return ModuleSettingsReceipt(
                receipt.module_id, receipt.package_digest, receipt.revision,
                receipt.effective_revision, SettingsApplyState.UNKNOWN,
                receipt.changed_fields, receipt.apply_classes,
                "module lifecycle changed before live apply",
            )
        handler = self._handlers.get((receipt.module_id, receipt.package_digest))
        if handler is None:
            return ModuleSettingsReceipt(
                receipt.module_id, receipt.package_digest, receipt.revision,
                receipt.effective_revision, SettingsApplyState.UNKNOWN,
                receipt.changed_fields, receipt.apply_classes,
                "no reviewed apply handler is registered",
            )
        try:
            handler(
                receipt.module_id, receipt.package_digest, values,
                receipt.changed_fields,
            )
        except Exception as exc:
            return ModuleSettingsReceipt(
                receipt.module_id, receipt.package_digest, receipt.revision,
                receipt.effective_revision, SettingsApplyState.FAILED,
                receipt.changed_fields, receipt.apply_classes, type(exc).__name__,
            )
        if not self._is_active_package(receipt.module_id, receipt.package_digest):
            return ModuleSettingsReceipt(
                receipt.module_id, receipt.package_digest, receipt.revision,
                receipt.effective_revision, SettingsApplyState.UNKNOWN,
                receipt.changed_fields, receipt.apply_classes,
                "module lifecycle changed during live apply; outcome is uncertain",
            )
        return ModuleSettingsReceipt(
            receipt.module_id, receipt.package_digest, receipt.revision,
            receipt.revision, SettingsApplyState.APPLIED,
            receipt.changed_fields, receipt.apply_classes,
        )

    def _is_active_package(self, module_id: str, package_digest: str) -> bool:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT package_digest,lifecycle FROM platform_module_lifecycle "
                "WHERE module_id=?", (module_id,),
            ).fetchone()
        return bool(
            row is not None
            and row["package_digest"] == package_digest
            and row["lifecycle"] == ModuleLifecycle.ACTIVE.value
        )

    def _settle(
        self, client_id: str, idempotency_key: str,
        receipt: ModuleSettingsReceipt,
    ) -> None:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT s.package_digest,s.revision,l.package_digest AS "
                "lifecycle_package,l.lifecycle FROM platform_module_settings_state s "
                "LEFT JOIN platform_module_lifecycle l ON l.module_id=s.module_id "
                "WHERE s.module_id=?", (receipt.module_id,),
            ).fetchone()
            if (
                current is None or current["package_digest"] != receipt.package_digest
                or int(current["revision"]) != receipt.revision
                or current["lifecycle_package"] != receipt.package_digest
                or current["lifecycle"] != ModuleLifecycle.ACTIVE.value
            ):
                receipt = ModuleSettingsReceipt(
                    receipt.module_id, receipt.package_digest, receipt.revision,
                    receipt.effective_revision, SettingsApplyState.UNKNOWN,
                    receipt.changed_fields, receipt.apply_classes,
                    "module settings changed while apply result was settling",
                )
            db.execute(
                "UPDATE platform_module_settings_request SET receipt_json=? WHERE "
                "module_id=? AND client_id=? AND idempotency_key=?",
                (self._json(receipt.to_payload()), receipt.module_id, client_id,
                 idempotency_key),
            )
            db.execute(
                "UPDATE platform_module_settings_event SET apply_state=?,"
                "effective_revision=?,error=? WHERE module_id=? AND revision=?",
                (receipt.apply_state.value, receipt.effective_revision,
                 receipt.error, receipt.module_id, receipt.revision),
            )
            if receipt.apply_state is SettingsApplyState.APPLIED:
                db.execute(
                    "UPDATE platform_module_settings_state SET effective_revision=? "
                    "WHERE module_id=? AND package_digest=? AND revision=?",
                    (receipt.revision, receipt.module_id, receipt.package_digest,
                     receipt.revision),
                )
            db.commit()

    @staticmethod
    def _receipt(payload: Mapping[str, object]) -> ModuleSettingsReceipt:
        return ModuleSettingsReceipt(
            str(payload["module_id"]), str(payload["package_digest"]),
            int(payload["revision"]), int(payload["effective_revision"]),
            SettingsApplyState(str(payload["apply_state"])),
            tuple(payload["changed_fields"]),  # type: ignore[arg-type]
            tuple(payload["apply_classes"]),  # type: ignore[arg-type]
            None if payload["error"] is None else str(payload["error"]),
        )

