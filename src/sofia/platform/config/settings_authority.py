"""Canonical, revisioned runtime settings authority.

The legacy settings row remains the one production value store.  This module
adds the protocol properties needed by remote clients: field ownership,
compare-and-swap, durable idempotency, append-only change events, and a
separate effective-application receipt.  It never gives a client a SQLite
handle and never treats a saved value as proof that the live runtime applied
it.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Callable, Mapping

from sofia.platform.config.user_settings import (
    RuntimeUserSettings, RuntimeUserSettingsStore,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard


class SettingsOwner(str, Enum):
    CORE = "core"
    HOST = "host"
    CLIENT = "client"


class SettingsApplyClass(str, Enum):
    LIVE = "live"
    NEXT_OPERATION = "next_operation"
    COMPONENT_RESTART = "component_restart"
    PLATFORM_RESTART = "platform_restart"


class SettingsApplyState(str, Enum):
    APPLIED = "applied"
    PENDING_NEXT_OPERATION = "pending_next_operation"
    PENDING_COMPONENT_RESTART = "pending_component_restart"
    PLATFORM_RESTART_REQUIRED = "platform_restart_required"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SettingsFieldContract:
    owner: SettingsOwner
    apply_class: SettingsApplyClass


# Client-only presentation fields intentionally never cross this canonical
# boundary.  Secrets are not RuntimeUserSettings fields at all.
_CLIENT_FIELDS = frozenset({
    "adaptive_theme", "avatar_renderer_enabled", "voice_output_enabled",
    "voice_input_enabled", "voice_muted", "voice_output_name",
    "voice_input_device",
})
_HOST_FIELDS = frozenset({
    "fleet_bootstrap", "fleet_discovery_enabled",
    "fleet_discovery_interval_seconds", "fleet_discovery_targets",
    "fleet_discovery_scopes", "fleet_discovery_max_hosts_per_scope",
})
_PLATFORM_RESTART_FIELDS = frozenset({"fleet_bootstrap"})
_COMPONENT_RESTART_FIELDS = frozenset({
    "provider_model", "provider_context_size", "provider_thinking",
    "provider_temperature", "provider_seed", "provider_max_output_tokens",
    "cognitive_routing_enabled", "cognitive_primary_model",
    "cognitive_secondary_model", "cognitive_primary_context_size",
    "cognitive_secondary_context_size", "cognitive_verify_enabled",
    "cognitive_model_auto_manage", "cognitive_model_auto_install",
    "cognitive_model_keep_alive", "cognitive_model_residency_mode",
    "idle_reflections_enabled", "habit_learning_enabled",
    "fleet_discovery_enabled", "fleet_discovery_interval_seconds",
    "fleet_discovery_targets", "fleet_discovery_scopes",
    "fleet_discovery_max_hosts_per_scope",
    "fleet_cognition", "discord_enabled", "discord_owner_user_id",
    "discord_bot_user_id", "discord_dm_channel_id",
})
_NEXT_OPERATION_FIELDS = frozenset({
    "outreach", "avatar_daily_outfit", "update_restart_mode",
    "cognitive_model_idle_unload_seconds",
    "cognitive_model_idle_preload_seconds",
})


def runtime_settings_contracts() -> dict[str, SettingsFieldContract]:
    raw = json.loads(RuntimeUserSettingsStore._encode(RuntimeUserSettings()))
    result: dict[str, SettingsFieldContract] = {}
    for field in raw:
        if field == "schema_version":
            continue
        owner = (
            SettingsOwner.CLIENT if field in _CLIENT_FIELDS
            else SettingsOwner.HOST if field in _HOST_FIELDS
            else SettingsOwner.CORE
        )
        apply_class = (
            SettingsApplyClass.PLATFORM_RESTART
            if field in _PLATFORM_RESTART_FIELDS
            else SettingsApplyClass.COMPONENT_RESTART
            if field in _COMPONENT_RESTART_FIELDS
            else SettingsApplyClass.NEXT_OPERATION
            if field in _NEXT_OPERATION_FIELDS
            else SettingsApplyClass.LIVE
        )
        result[field] = SettingsFieldContract(owner, apply_class)
    return result


@dataclass(frozen=True, slots=True)
class SettingsReceipt:
    revision: int
    effective_revision: int
    apply_state: SettingsApplyState
    changed_fields: tuple[str, ...]
    apply_classes: tuple[str, ...]
    error: str | None

    def to_payload(self) -> dict[str, object]:
        return {
            "revision": self.revision,
            "effective_revision": self.effective_revision,
            "apply_state": self.apply_state.value,
            "changed_fields": list(self.changed_fields),
            "apply_classes": list(self.apply_classes),
            "error": self.error,
        }


LiveApply = Callable[[RuntimeUserSettings, tuple[str, ...]], None]


class CanonicalSettingsService:
    """CAS settings service over the existing canonical runtime row."""

    def __init__(self, state_path, *, live_apply: LiveApply | None = None) -> None:
        self.path = state_path
        self._guard = CanonicalSQLiteGuard(state_path)
        self._settings = RuntimeUserSettingsStore(state_path)
        self._live_apply = live_apply
        self.contracts = runtime_settings_contracts()
        with closing(self._connect()) as db, db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS platform_settings_state(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    revision INTEGER NOT NULL,
                    effective_revision INTEGER NOT NULL,
                    value_digest TEXT,
                    value_json TEXT,
                    updated_at TEXT NOT NULL
                );
                INSERT OR IGNORE INTO platform_settings_state(
                    singleton,revision,effective_revision,updated_at
                ) VALUES(1,0,0,'1970-01-01T00:00:00+00:00');
                CREATE TABLE IF NOT EXISTS platform_settings_request(
                    client_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(client_id,idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS platform_settings_event(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    revision INTEGER NOT NULL UNIQUE,
                    client_id TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    audience_id TEXT NOT NULL,
                    changed_fields_json TEXT NOT NULL,
                    apply_state TEXT NOT NULL,
                    effective_revision INTEGER NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            columns = {
                row[1] for row in db.execute(
                    "PRAGMA table_info(platform_settings_state)"
                ).fetchall()
            }
            if "value_digest" not in columns:
                db.execute("ALTER TABLE platform_settings_state ADD COLUMN value_digest TEXT")
            if "value_json" not in columns:
                db.execute("ALTER TABLE platform_settings_state ADD COLUMN value_json TEXT")
            db.execute("BEGIN IMMEDIATE")
            self._sync_locked(db, now=datetime.now(timezone.utc))

    def _connect(self):
        db = self._guard.connect(timeout=10)
        db.row_factory = __import__("sqlite3").Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )

    def snapshot(self, *, owners: frozenset[SettingsOwner]) -> dict[str, object]:
        if not owners:
            raise PermissionError("no settings read scope")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._sync_locked(db, now=datetime.now(timezone.utc))
            row_value = db.execute(
                "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
                (RuntimeUserSettingsStore._KEY,),
            ).fetchone()
            settings = json.loads(
                RuntimeUserSettingsStore._encode(RuntimeUserSettings())
                if row_value is None else row_value["value_json"]
            )
            row = db.execute(
                "SELECT revision,effective_revision FROM platform_settings_state WHERE singleton=1"
            ).fetchone()
        values = {
            field: value for field, value in settings.items()
            if field != "schema_version" and self.contracts[field].owner in owners
        }
        return {
            "schema_version": settings["schema_version"],
            "revision": int(row["revision"]),
            "effective_revision": int(row["effective_revision"]),
            "values": values,
            "contracts": {
                field: {
                    "owner": self.contracts[field].owner.value,
                    "apply_class": self.contracts[field].apply_class.value,
                }
                for field in sorted(values)
            },
        }

    def update(
        self, *, client_id: str, principal_id: str, audience_id: str,
        idempotency_key: str, expected_revision: int,
        changes: Mapping[str, object], writable_owners: frozenset[SettingsOwner],
        now: datetime,
    ) -> SettingsReceipt:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be nonnegative")
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError("settings changes must be a nonempty object")
        if len(changes) > 64:
            raise ValueError("too many settings changes")
        if any(not isinstance(field, str) for field in changes):
            raise ValueError("settings field names must be strings")
        fields = tuple(sorted(changes))
        for field in fields:
            contract = self.contracts.get(field)
            if contract is None or contract.owner is SettingsOwner.CLIENT:
                raise PermissionError(f"{field} is not writable through canonical settings")
            if contract.owner not in writable_owners:
                raise PermissionError(f"settings scope does not allow {field}")
        if (
            not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("settings update timestamp must be timezone-aware")
        moment = now.astimezone(timezone.utc)
        request_document = {
            "expected_revision": expected_revision,
            "changes": dict(changes),
        }
        digest = sha256(self._json(request_document).encode("utf-8")).hexdigest()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._sync_locked(db, now=moment)
            prior = db.execute(
                "SELECT request_digest,receipt_json FROM platform_settings_request "
                "WHERE client_id=? AND idempotency_key=?",
                (client_id, idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior["request_digest"] != digest:
                    db.rollback()
                    raise RuntimeError("settings idempotency key payload conflict")
                db.commit()
                return self._receipt(json.loads(prior["receipt_json"]))
            state = db.execute(
                "SELECT revision,effective_revision FROM platform_settings_state WHERE singleton=1"
            ).fetchone()
            if int(state["revision"]) != expected_revision:
                db.rollback()
                raise RuntimeError("settings revision conflict")
            row = db.execute(
                "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
                (RuntimeUserSettingsStore._KEY,),
            ).fetchone()
            current = (
                json.loads(RuntimeUserSettingsStore._encode(RuntimeUserSettings()))
                if row is None else json.loads(row["value_json"])
            )
            current.update(dict(changes))
            # The canonical decoder performs all nested and scalar validation.
            candidate = RuntimeUserSettingsStore._decode(self._json(current))
            revision = expected_revision + 1
            classes = tuple(sorted({self.contracts[field].apply_class.value for field in fields}))
            apply_state = self._initial_apply_state(fields)
            receipt = SettingsReceipt(
                revision, int(state["effective_revision"]), apply_state,
                fields, classes, None,
            )
            self._settings.save(candidate, at=moment, connection=db)
            encoded_candidate = RuntimeUserSettingsStore._encode(candidate)
            db.execute(
                "UPDATE platform_settings_state SET revision=?,value_digest=?,"
                "value_json=?,updated_at=? WHERE singleton=1",
                (revision, sha256(encoded_candidate.encode("utf-8")).hexdigest(),
                 encoded_candidate, moment.isoformat()),
            )
            db.execute(
                "INSERT INTO platform_settings_event(revision,client_id,principal_id,"
                "audience_id,changed_fields_json,apply_state,effective_revision,error,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (revision, client_id, principal_id, audience_id,
                 self._json(list(fields)), apply_state.value,
                 receipt.effective_revision, None, moment.isoformat()),
            )
            db.execute(
                "INSERT INTO platform_settings_request(client_id,idempotency_key,"
                "request_digest,receipt_json,created_at) VALUES(?,?,?,?,?)",
                (client_id, idempotency_key, digest,
                 self._json(receipt.to_payload()), moment.isoformat()),
            )
            db.commit()

        if all(self.contracts[field].apply_class is SettingsApplyClass.LIVE for field in fields):
            receipt = self._apply_live(candidate, receipt)
            self._settle(client_id, idempotency_key, receipt)
        return receipt

    def _initial_apply_state(self, fields: tuple[str, ...]) -> SettingsApplyState:
        classes = {self.contracts[field].apply_class for field in fields}
        if SettingsApplyClass.PLATFORM_RESTART in classes:
            return SettingsApplyState.PLATFORM_RESTART_REQUIRED
        if SettingsApplyClass.COMPONENT_RESTART in classes:
            return SettingsApplyState.PENDING_COMPONENT_RESTART
        if SettingsApplyClass.NEXT_OPERATION in classes:
            return SettingsApplyState.PENDING_NEXT_OPERATION
        return SettingsApplyState.UNKNOWN

    def _apply_live(
        self, settings: RuntimeUserSettings, receipt: SettingsReceipt,
    ) -> SettingsReceipt:
        if self._live_apply is None:
            return SettingsReceipt(
                receipt.revision, receipt.effective_revision,
                SettingsApplyState.UNKNOWN, receipt.changed_fields,
                receipt.apply_classes, "no live apply handler is registered",
            )
        try:
            self._live_apply(settings, receipt.changed_fields)
        except Exception as exc:
            return SettingsReceipt(
                receipt.revision, receipt.effective_revision,
                SettingsApplyState.FAILED, receipt.changed_fields,
                receipt.apply_classes, type(exc).__name__,
            )
        return SettingsReceipt(
            receipt.revision, receipt.revision, SettingsApplyState.APPLIED,
            receipt.changed_fields, receipt.apply_classes, None,
        )

    def _settle(
        self, client_id: str, idempotency_key: str, receipt: SettingsReceipt,
    ) -> None:
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE platform_settings_request SET receipt_json=? "
                "WHERE client_id=? AND idempotency_key=?",
                (self._json(receipt.to_payload()), client_id, idempotency_key),
            )
            db.execute(
                "UPDATE platform_settings_event SET apply_state=?,effective_revision=?,error=? "
                "WHERE revision=?",
                (receipt.apply_state.value, receipt.effective_revision,
                 receipt.error, receipt.revision),
            )
            if receipt.apply_state is SettingsApplyState.APPLIED:
                db.execute(
                    "UPDATE platform_settings_state SET effective_revision=? "
                    "WHERE singleton=1 AND effective_revision<?",
                    (receipt.revision, receipt.revision),
                )
            db.commit()

    @staticmethod
    def _receipt(payload: Mapping[str, object]) -> SettingsReceipt:
        return SettingsReceipt(
            revision=int(payload["revision"]),
            effective_revision=int(payload["effective_revision"]),
            apply_state=SettingsApplyState(str(payload["apply_state"])),
            changed_fields=tuple(payload["changed_fields"]),  # type: ignore[arg-type]
            apply_classes=tuple(payload["apply_classes"]),  # type: ignore[arg-type]
            error=None if payload["error"] is None else str(payload["error"]),
        )

    def _sync_locked(self, db, *, now: datetime) -> None:
        """Import a legacy trusted local write into the revision sequence.

        This compatibility bridge prevents the old local Settings window or a
        reviewed internal caller from changing the canonical row behind a
        remote client's CAS token.  It grants no remote authority.
        """
        row_value = db.execute(
            "SELECT value_json FROM ui_runtime_settings WHERE settings_key=?",
            (RuntimeUserSettingsStore._KEY,),
        ).fetchone()
        current_json = (
            RuntimeUserSettingsStore._encode(RuntimeUserSettings())
            if row_value is None else str(row_value["value_json"])
        )
        # Reject corrupt legacy state before recording it as a revision.
        RuntimeUserSettingsStore._decode(current_json)
        digest = sha256(current_json.encode("utf-8")).hexdigest()
        state = db.execute(
            "SELECT revision,effective_revision,value_digest,value_json "
            "FROM platform_settings_state WHERE singleton=1"
        ).fetchone()
        if state["value_digest"] is None:
            db.execute(
                "UPDATE platform_settings_state SET value_digest=?,value_json=? "
                "WHERE singleton=1", (digest, current_json),
            )
            return
        if state["value_digest"] == digest:
            return
        previous = json.loads(state["value_json"] or "{}")
        current = json.loads(current_json)
        fields = tuple(sorted(
            field for field in self.contracts
            if previous.get(field) != current.get(field)
        ))
        revision = int(state["revision"]) + 1
        moment = now.astimezone(timezone.utc)
        db.execute(
            "UPDATE platform_settings_state SET revision=?,value_digest=?,"
            "value_json=?,updated_at=? WHERE singleton=1",
            (revision, digest, current_json, moment.isoformat()),
        )
        db.execute(
            "INSERT INTO platform_settings_event(revision,client_id,principal_id,"
            "audience_id,changed_fields_json,apply_state,effective_revision,error,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (revision, "platform:legacy-local", "principal:local-operator",
             "audience:local", self._json(list(fields)),
             SettingsApplyState.UNKNOWN.value, int(state["effective_revision"]),
             "legacy local write requires runtime reconciliation",
             moment.isoformat()),
        )

    def events(
        self, *, after_revision: int, owners: frozenset[SettingsOwner], limit: int,
    ) -> list[dict[str, object]]:
        if type(after_revision) is not int or after_revision < 0:
            raise ValueError("after_revision must be nonnegative")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("event limit must be in 1..200")
        if not owners:
            raise PermissionError("no settings read scope")
        events: list[dict[str, object]] = []
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._sync_locked(db, now=datetime.now(timezone.utc))
            rows = db.execute(
                "SELECT * FROM platform_settings_event WHERE revision>? "
                "ORDER BY revision LIMIT ?", (after_revision, limit),
            ).fetchall()
        for row in rows:
            fields = tuple(json.loads(row["changed_fields_json"]))
            visible = tuple(
                field for field in fields if self.contracts[field].owner in owners
            )
            if visible:
                events.append({
                    "revision": int(row["revision"]),
                    "effective_revision": int(row["effective_revision"]),
                    "changed_fields": list(visible),
                    "apply_state": row["apply_state"], "error": row["error"],
                    "created_at": row["created_at"],
                })
        return events
