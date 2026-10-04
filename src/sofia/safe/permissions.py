"""Unified project permission policy, standing grants, and private/adult authority."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, IntEnum
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from sofia.safe.audit import AuditChain


class PermissionLevel(IntEnum):
    OBSERVE_READ = 1
    SAFE_AUTONOMOUS = 2
    REVERSIBLE_SCOPED = 3
    PROTECTED = 4
    NEVER_SELF_AUTHORIZED = 5


class PrivacyClass(str, Enum):
    PUBLIC = "public"
    PERSONAL = "personal"
    PRIVATE = "private"
    ADULT = "adult"
    PRIVATE_ADULT = "private_adult"
    PROTECTED_PRIVATE = "protected_private"


@dataclass(frozen=True, slots=True)
class CapabilityPermissionPolicy:
    capability: str
    level: PermissionLevel
    privacy: PrivacyClass = PrivacyClass.PRIVATE
    standing_grant_allowed: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.capability, str) or not self.capability.strip():
            raise ValueError("capability must be nonempty")
        if not isinstance(self.level, PermissionLevel):
            raise TypeError("level must be PermissionLevel")
        if not isinstance(self.privacy, PrivacyClass):
            raise TypeError("privacy must be PrivacyClass")
        if self.standing_grant_allowed and self.level is not PermissionLevel.REVERSIBLE_SCOPED:
            raise ValueError(
                "standing grants are only valid for level-3 reversible capabilities"
            )


@dataclass(frozen=True, slots=True)
class StandingPermissionGrant:
    grant_id: str
    capability: str
    scope: dict[str, Any]
    granted_by: str
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.is_active_at(datetime.now(timezone.utc))

    def is_active_at(self, now: datetime) -> bool:
        moment = now.astimezone(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and moment >= self.expires_at.astimezone(timezone.utc):
            return False
        return moment >= self.granted_at.astimezone(timezone.utc)

    def matches(self, parameters: dict[str, Any], *, now: datetime) -> bool:
        if not self.is_active_at(now):
            return False
        return all(parameters.get(key) == expected for key, expected in self.scope.items())


@dataclass(frozen=True, slots=True)
class AdultPrivateAuthority:
    private_chat: bool = True
    adult_chat: bool = False
    adult_avatar: bool = False
    adult_external_delivery: bool = False
    updated_by: str = "system:bootstrap"
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in (
            "private_chat",
            "adult_chat",
            "adult_avatar",
            "adult_external_delivery",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if not isinstance(self.updated_by, str) or not self.updated_by.strip():
            raise ValueError("updated_by must be nonempty")
        if self.updated_at is not None and (
            self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None
        ):
            raise ValueError("updated_at must be timezone-aware")


_READ_ONLY = frozenset({
    "tool.catalog",
    "permissions.inspect",
    "codebase.inspect",
    "filesystem.inspect",
    "filesystem.changes",
    "process.inspect",
    "system.inspect",
    "network.inspect",
    "network.discover",
    "service.inspect",
    "hardware.inspect",
    "machine.list",
    "machine.get",
    "machine.discover.local",
    "ops.fleet.list",
    "ops.fleet.get",
    "ops.fleet.enrollment_evidence",
    "ops.telemetry.latest",
    "ops.placement.choose",
    "ops.drift.detect",
    "ops.drift.propose",
    "ops.reconcile.preview",
    "ops.reconcile.active",
    "ops.migration.plan",
    "ops.maintenance.receipt",
    "remote.nodes",
    "remote.process.inspect",
    "remote.system.inspect",
    "remote.network.inspect",
    "remote.service.inspect",
    "remote.hardware.inspect",
    "remote.vm.list",
    "remote.vm.get",
    "remote.container.list",
    "remote.container.get",
    "remote.ollama.inference_policy",
    "remote.ollama.models",
    "remote.ollama.running",
    "remote.ollama.show",
    "home_assistant.services",
    "home_assistant.states",
    "home_assistant.state",
    "portainer.endpoints",
    "portainer.containers",
    "portainer.container",
    "portainer.container.stats",
    "portainer.info",
    "portainer.summary",
    "portainer.images",
    "portainer.volumes",
    "portainer.networks",
    "portainer.stacks",
    "jmri.power",
    "jmri.roster",
    "jmri.object",
    "github.repository",
    "github.issues",
    "github.file",
    "github.pull_requests",
    "ollama.models",
    "ollama.running",
    "ollama.model.show",
    "discord.status",
    "storage.roots",
    "storage.usage",
    "storage.list",
    "storage.read_text",
    "sqlite.state.tables",
    "sqlite.state.query",
    "sqlite.state.integrity",
    "knowledge.search",
    "knowledge.document",
    "dev.status",
    "dev.candidates.list",
    "dev.candidate.get",
    "hyperv.vms",
    "hyperv.vm",
    "environment.nws.read",
    "environment.home_assistant.read",
})

_SAFE_AUTONOMOUS = frozenset({
    "machine.refresh.local",
    "ops.fleet.discover",
    "sqlite.state.backup",
    "sqlite.state.wal_checkpoint",
    "sqlite.state.vacuum",
    "knowledge.ingest.text",
    "knowledge.ingest.pdf",
    "dev.build",
})

_REVERSIBLE = frozenset({
    "notification.send",
    "portainer.container.restart",
    "jmri.power.set",
    "github.issue.create",
    "github.pull_request.create",
    "discord.pause",
    "discord.resume",
    "local.service.start",
    "local.service.stop",
    "local.service.restart",
    "hyperv.vm.start",
    "hyperv.vm.stop",
    "storage.write_text",
    "storage.mkdir",
    "storage.copy",
    "storage.move",
    "knowledge.document.write",
})

_PROTECTED = frozenset({
    "fleet.enroll",
    "home_assistant.service.call",
    "github.pull_request.merge",
    "discord.revoke",
    "local.host.reboot",
    "local.package.update",
    "storage.delete",
    "remote.service.start",
    "remote.service.stop",
    "remote.service.restart",
    "remote.vm.start",
    "remote.vm.stop",
    "remote.container.restart",
    "remote.ollama.pull",
    "remote.ollama.load",
    "remote.ollama.unload",
    "remote.host.reboot",
    "remote.package.update",
    "dev.apply",
    "dev.rollback",
    "dev.commit",
    "dev.push",
})

_NEVER_SELF_AUTHORIZED = frozenset({
    "permissions.grant",
    "permissions.revoke",
    "permissions.classify",
    "privacy.authority.change",
    "fleet.trust-policy.change",
})


def explicitly_classified_capabilities() -> frozenset[str]:
    """Return capability names assigned an intentional project permission level."""
    return frozenset(
        _READ_ONLY
        | _SAFE_AUTONOMOUS
        | _REVERSIBLE
        | _PROTECTED
        | _NEVER_SELF_AUTHORIZED
    )


def is_explicitly_classified(capability: str) -> bool:
    if not isinstance(capability, str) or not capability.strip():
        return False
    return capability in explicitly_classified_capabilities()


def capability_permission_policy(capability: str) -> CapabilityPermissionPolicy:
    if not isinstance(capability, str) or not capability.strip():
        raise ValueError("capability must be nonempty")
    if capability in _READ_ONLY:
        return CapabilityPermissionPolicy(
            capability,
            PermissionLevel.OBSERVE_READ,
            PrivacyClass.PRIVATE,
            False,
            "Read-only observation or planning.",
        )
    if capability in _SAFE_AUTONOMOUS:
        return CapabilityPermissionPolicy(
            capability,
            PermissionLevel.SAFE_AUTONOMOUS,
            PrivacyClass.PRIVATE,
            False,
            "Bounded low-risk maintenance.",
        )
    if capability in _REVERSIBLE:
        return CapabilityPermissionPolicy(
            capability,
            PermissionLevel.REVERSIBLE_SCOPED,
            PrivacyClass.PRIVATE,
            True,
            "Reversible change allowed by exact approval or scoped standing grant.",
        )
    if capability in _NEVER_SELF_AUTHORIZED:
        return CapabilityPermissionPolicy(
            capability,
            PermissionLevel.NEVER_SELF_AUTHORIZED,
            PrivacyClass.PROTECTED_PRIVATE,
            False,
            "Authority-changing operation that Sofía may never self-authorize.",
        )
    if capability in _PROTECTED:
        return CapabilityPermissionPolicy(
            capability,
            PermissionLevel.PROTECTED,
            PrivacyClass.PRIVATE,
            False,
            "Protected change requiring exact approval.",
        )
    return CapabilityPermissionPolicy(
        capability,
        PermissionLevel.PROTECTED,
        PrivacyClass.PRIVATE,
        False,
        "Unknown capabilities fail closed as protected.",
    )


def automatic_capabilities() -> tuple[str, ...]:
    """Capabilities exposed without per-use approval."""
    return tuple(sorted(_READ_ONLY | _SAFE_AUTONOMOUS))


def grantable_capabilities() -> tuple[str, ...]:
    return tuple(sorted(_REVERSIBLE))


class PermissionStore:
    """Canonical SQLite authority for standing grants and private/adult settings."""

    def __init__(self, state_path: Path | str) -> None:
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.audit = AuditChain(self.path)
        with closing(self._connect()) as db, db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS safe_permission_grant (
                    grant_id TEXT PRIMARY KEY,
                    capability TEXT NOT NULL,
                    scope_json TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked_at TEXT
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS safe_private_adult_authority (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    private_chat INTEGER NOT NULL CHECK(private_chat IN (0,1)),
                    adult_chat INTEGER NOT NULL CHECK(adult_chat IN (0,1)),
                    adult_avatar INTEGER NOT NULL CHECK(adult_avatar IN (0,1)),
                    adult_external_delivery INTEGER NOT NULL
                        CHECK(adult_external_delivery IN (0,1)),
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            row = db.execute(
                "SELECT 1 FROM safe_private_adult_authority WHERE singleton=1"
            ).fetchone()
            if row is None:
                now = datetime.now(timezone.utc)
                db.execute(
                    """
                    INSERT INTO safe_private_adult_authority (
                        singleton, private_chat, adult_chat, adult_avatar,
                        adult_external_delivery, updated_by, updated_at
                    ) VALUES (1,1,0,0,0,?,?)
                    """,
                    ("system:bootstrap", now.isoformat()),
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _require_sparks(actor: str) -> None:
        if actor != "Sparks":
            raise PermissionError("permission authority belongs to Sparks")

    @staticmethod
    def _scope_json(scope: dict[str, Any]) -> str:
        if not isinstance(scope, dict):
            raise TypeError("scope must be a dict")
        if any(not isinstance(key, str) or not key.strip() for key in scope):
            raise ValueError("scope keys must be nonempty strings")
        try:
            return json.dumps(
                scope,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("scope must contain JSON-serializable values") from exc

    def grant(
        self,
        capability: str,
        *,
        scope: dict[str, Any] | None = None,
        granted_by: str = "Sparks",
        expires_at: datetime | None = None,
        grant_id: str | None = None,
        now: datetime | None = None,
    ) -> StandingPermissionGrant:
        self._require_sparks(granted_by)
        policy = capability_permission_policy(capability)
        if not policy.standing_grant_allowed:
            raise PermissionError(
                f"{capability} does not permit standing grants at level {int(policy.level)}"
            )
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if expires_at is not None:
            if expires_at.tzinfo is None or expires_at.utcoffset() is None:
                raise ValueError("expires_at must be timezone-aware")
            expires_at = expires_at.astimezone(timezone.utc)
            if expires_at <= moment:
                raise ValueError("expires_at must be in the future")
        identifier = grant_id or str(uuid4())
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("grant_id must be nonempty")
        normalized_scope = dict(scope or {})
        encoded_scope = self._scope_json(normalized_scope)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                INSERT INTO safe_permission_grant (
                    grant_id, capability, scope_json, granted_by,
                    granted_at, expires_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    identifier,
                    capability,
                    encoded_scope,
                    granted_by,
                    moment.isoformat(),
                    None if expires_at is None else expires_at.isoformat(),
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=granted_by,
                event_type="permission.standing_grant.created",
                payload={
                    "grant_id": identifier,
                    "capability": capability,
                    "scope": normalized_scope,
                    "expires_at": (
                        None if expires_at is None else expires_at.isoformat()
                    ),
                },
                occurred_at=moment,
                event_id=f"permission-grant:{identifier}",
            )
        return StandingPermissionGrant(
            identifier,
            capability,
            normalized_scope,
            granted_by,
            moment,
            expires_at,
            None,
        )

    def revoke(
        self,
        grant_id: str,
        *,
        revoked_by: str = "Sparks",
        now: datetime | None = None,
    ) -> StandingPermissionGrant:
        self._require_sparks(revoked_by)
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT grant_id,capability,scope_json,granted_by,granted_at,
                       expires_at,revoked_at
                FROM safe_permission_grant
                WHERE grant_id=?
                """,
                (grant_id,),
            ).fetchone()
            if row is None:
                raise KeyError(grant_id)
            if row["revoked_at"] is not None:
                raise PermissionError("standing grant is already revoked")
            changed = db.execute(
                "UPDATE safe_permission_grant SET revoked_at=? "
                "WHERE grant_id=? AND revoked_at IS NULL",
                (moment.isoformat(), grant_id),
            )
            if changed.rowcount != 1:
                raise RuntimeError("standing grant could not be revoked")
            self.audit.append_in_transaction(
                db,
                actor_id=revoked_by,
                event_type="permission.standing_grant.revoked",
                payload={"grant_id": grant_id, "capability": row["capability"]},
                occurred_at=moment,
                event_id=f"permission-revoke:{grant_id}",
            )
            return self._row_to_grant(row, revoked_at=moment)

    @staticmethod
    def _row_to_grant(
        row: sqlite3.Row,
        *,
        revoked_at: datetime | None = None,
    ) -> StandingPermissionGrant:
        return StandingPermissionGrant(
            grant_id=row["grant_id"],
            capability=row["capability"],
            scope=json.loads(row["scope_json"]),
            granted_by=row["granted_by"],
            granted_at=datetime.fromisoformat(row["granted_at"]),
            expires_at=(
                None if row["expires_at"] is None
                else datetime.fromisoformat(row["expires_at"])
            ),
            revoked_at=(
                revoked_at
                if revoked_at is not None
                else (
                    None if row["revoked_at"] is None
                    else datetime.fromisoformat(row["revoked_at"])
                )
            ),
        )

    def grants(self, *, active_only: bool = False) -> tuple[StandingPermissionGrant, ...]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT grant_id,capability,scope_json,granted_by,granted_at,
                       expires_at,revoked_at
                FROM safe_permission_grant
                ORDER BY granted_at, grant_id
                """
            ).fetchall()
        grants = tuple(self._row_to_grant(row) for row in rows)
        if not active_only:
            return grants
        now = datetime.now(timezone.utc)
        return tuple(grant for grant in grants if grant.is_active_at(now))

    def allows_standing(
        self,
        capability: str,
        parameters: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> bool:
        policy = capability_permission_policy(capability)
        if not policy.standing_grant_allowed:
            return False
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return any(
            grant.capability == capability and grant.matches(parameters, now=moment)
            for grant in self.grants(active_only=False)
        )

    def private_adult_authority(self) -> AdultPrivateAuthority:
        with closing(self._connect()) as db:
            row = db.execute(
                """
                SELECT private_chat,adult_chat,adult_avatar,
                       adult_external_delivery,updated_by,updated_at
                FROM safe_private_adult_authority
                WHERE singleton=1
                """
            ).fetchone()
        if row is None:
            raise RuntimeError("private/adult authority state is missing")
        return AdultPrivateAuthority(
            private_chat=bool(row["private_chat"]),
            adult_chat=bool(row["adult_chat"]),
            adult_avatar=bool(row["adult_avatar"]),
            adult_external_delivery=bool(row["adult_external_delivery"]),
            updated_by=row["updated_by"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def set_private_adult_authority(
        self,
        *,
        private_chat: bool,
        adult_chat: bool,
        adult_avatar: bool,
        adult_external_delivery: bool,
        updated_by: str = "Sparks",
        now: datetime | None = None,
    ) -> AdultPrivateAuthority:
        self._require_sparks(updated_by)
        for name, value in (
            ("private_chat", private_chat),
            ("adult_chat", adult_chat),
            ("adult_avatar", adult_avatar),
            ("adult_external_delivery", adult_external_delivery),
        ):
            if type(value) is not bool:
                raise TypeError(f"{name} must be bool")
        if adult_external_delivery and not (adult_chat or adult_avatar):
            raise ValueError(
                "adult external delivery requires adult chat or adult avatar authority"
            )
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE safe_private_adult_authority
                SET private_chat=?,adult_chat=?,adult_avatar=?,
                    adult_external_delivery=?,updated_by=?,updated_at=?
                WHERE singleton=1
                """,
                (
                    int(private_chat),
                    int(adult_chat),
                    int(adult_avatar),
                    int(adult_external_delivery),
                    updated_by,
                    moment.isoformat(),
                ),
            )
            self.audit.append_in_transaction(
                db,
                actor_id=updated_by,
                event_type="permission.private_adult.updated",
                payload={
                    "private_chat": private_chat,
                    "adult_chat": adult_chat,
                    "adult_avatar": adult_avatar,
                    "adult_external_delivery": adult_external_delivery,
                },
                occurred_at=moment,
            )
        return self.private_adult_authority()
