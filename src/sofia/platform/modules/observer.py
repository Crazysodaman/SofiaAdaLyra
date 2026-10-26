"""Read-only Core observation adapter for canonical module lifecycle state."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from sofia.core.modreg.platform import (
    ModuleDescribeObservation,
    ModuleHealthObservation,
    ModuleObservationKind,
    OutcomeObservation,
    OutcomePage,
    OutcomeStatus,
    PlacementMode,
    PlacementObservation,
    PlatformModuleObserver,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard
from sofia.platform.safe.permissions import (
    PermissionLevel,
    capability_permission_policy,
)

from .lifecycle import ModuleLifecycle


_INSTALLED = frozenset({
    ModuleLifecycle.STAGED.value,
    ModuleLifecycle.INSTALLED_DISABLED.value,
    ModuleLifecycle.ACTIVATING.value,
    ModuleLifecycle.ACTIVE.value,
    ModuleLifecycle.DRAINING.value,
    ModuleLifecycle.PAUSED.value,
    ModuleLifecycle.QUARANTINED.value,
    ModuleLifecycle.UPDATING.value,
    ModuleLifecycle.ROLLING_BACK.value,
})
_OUTCOME_LIMIT = 200
_OUTCOME_CURSOR_PREFIX = "module-attempt:"


class CanonicalPlatformModuleObserver(PlatformModuleObserver):
    """Project canonical Platform rows without granting or executing anything.

    Missing lifecycle tables mean no installed-module observation, not an
    error and not proof that a package does not exist elsewhere. Historical
    ACTIVE rows are never reported as live health after their freshness
    window; the runtime supervisor must produce a new observation.
    """

    def __init__(
        self, state_path: Path | str, *,
        max_active_age: timedelta = timedelta(minutes=2),
        host_identity: str = "local-platform",
    ) -> None:
        if not isinstance(state_path, (Path, str)):
            raise TypeError("state_path must be a Path or path string")
        if not isinstance(max_active_age, timedelta) or max_active_age <= timedelta(0):
            raise ValueError("max_active_age must be positive")
        if not isinstance(host_identity, str) or not host_identity.strip():
            raise ValueError("host_identity required")
        self._guard = CanonicalSQLiteGuard(Path(state_path))
        self.max_active_age = max_active_age
        self.host_identity = host_identity

    def _snapshot(
        self,
    ) -> tuple[tuple[sqlite3.Row, ...], dict[str, tuple[str, ...]]]:
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='platform_module_lifecycle'"
            ).fetchone()
            if exists is None:
                return (), {}
            rows = db.execute(
                "SELECT module_id,version,lifecycle,active_profile,updated_at "
                "FROM platform_module_lifecycle ORDER BY module_id"
            ).fetchall()
            capability_table = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='platform_module_capability'"
            ).fetchone()
            capability_rows = (
                ()
                if capability_table is None
                else db.execute(
                    "SELECT module_id,capability_id "
                    "FROM platform_module_capability "
                    "ORDER BY module_id,capability_id"
                ).fetchall()
            )
        capabilities: dict[str, list[str]] = {}
        for row in capability_rows:
            capabilities.setdefault(str(row["module_id"]), []).append(
                str(row["capability_id"])
            )
        return tuple(rows), {
            module_id: tuple(names)
            for module_id, names in capabilities.items()
        }

    def _rows(self) -> tuple[sqlite3.Row, ...]:
        return self._snapshot()[0]

    def _verified_runtime_observations(self) -> dict[str, sqlite3.Row]:
        """Latest authenticated adapter probe recorded by canonical RUN."""
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            tables = {
                row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name IN ('platform_module_operation_request',"
                    "'platform_module_operation_attempt')"
                )
            }
            if len(tables) != 2:
                return {}
            rows = db.execute(
                """SELECT request.module_id,request.component_id,
                          request.host_identity,attempt.evidence_ref,
                          attempt.occurred_at
                   FROM platform_module_operation_attempt AS attempt
                   JOIN platform_module_operation_request AS request
                     ON request.request_id=attempt.request_id
                   JOIN platform_module_lifecycle AS lifecycle
                     ON lifecycle.module_id=request.module_id
                    AND lifecycle.package_digest=request.package_digest
                    AND lifecycle.revision=request.expected_revision+2
                    AND lifecycle.active_profile=request.profile
                    AND lifecycle.lifecycle='active'
                   WHERE attempt.status='externally_verified_success'
                     AND request.operation IN ('activate','resume')
                   ORDER BY attempt.occurred_at DESC,attempt.event_id DESC"""
            ).fetchall()
        result: dict[str, sqlite3.Row] = {}
        for row in rows:
            result.setdefault(str(row["module_id"]), row)
        return result

    def described(self) -> tuple[ModuleDescribeObservation, ...]:
        now = datetime.now(timezone.utc)
        rows, declared = self._snapshot()
        result = []
        for row in rows:
            if str(row["lifecycle"]) not in _INSTALLED:
                continue
            module_id = str(row["module_id"])
            capabilities = declared.get(module_id, ())
            profile = (
                "DISABLED" if row["active_profile"] is None
                else str(row["active_profile"])
            )
            requires_permission = frozenset(
                capability
                for capability in capabilities
                if capability_permission_policy(capability).level
                > PermissionLevel.SAFE_AUTONOMOUS
            )
            simulated_only = (
                frozenset(capabilities)
                if profile.casefold() == "simulate" else frozenset()
            )
            result.append(ModuleDescribeObservation(
                module_id=module_id,
                version=str(row["version"]),
                capabilities=capabilities,
                requires_permission=requires_permission,
                active_profile=profile,
                simulated_only=simulated_only,
                observed_at=now,
            ))
        return tuple(
            result
        )

    def health(self) -> tuple[ModuleHealthObservation, ...]:
        now = datetime.now(timezone.utc)
        runtime = self._verified_runtime_observations()
        result = []
        for row in self._rows():
            lifecycle = str(row["lifecycle"])
            if lifecycle == ModuleLifecycle.REMOVED.value:
                continue
            observation = runtime.get(str(row["module_id"]))
            observed_at = (
                None if observation is None
                else datetime.fromisoformat(str(observation["occurred_at"])).astimezone(
                    timezone.utc
                )
            )
            fresh_active = (
                lifecycle == ModuleLifecycle.ACTIVE.value
                and observed_at is not None
                and -timedelta(seconds=5) <= now - observed_at <= self.max_active_age
            )
            if fresh_active:
                kind = ModuleObservationKind.HEALTHY
                projected_lifecycle = "ACTIVE"
                reasons = ("verified-adapter-observation",)
            elif lifecycle == ModuleLifecycle.QUARANTINED.value:
                kind = ModuleObservationKind.QUARANTINED
                projected_lifecycle = "QUARANTINED"
                reasons = ("platform-lifecycle-quarantined",)
            else:
                kind = ModuleObservationKind.UNKNOWN_STATE
                projected_lifecycle = lifecycle.upper()
                reasons = (
                    "active-observation-missing-or-stale"
                    if lifecycle == ModuleLifecycle.ACTIVE.value
                    else f"lifecycle:{lifecycle}",
                )
            result.append(ModuleHealthObservation(
                module_instance_id=(
                    str(row["module_id"])
                    if observation is None
                    else f'{row["module_id"]}@{observation["component_id"]}'
                ),
                host_identity=(
                    self.host_identity
                    if observation is None else str(observation["host_identity"])
                ),
                lifecycle=projected_lifecycle,
                health=kind,
                reason_codes=reasons,
                blocked_dependencies=(),
                fresh_until=(
                    now + timedelta(seconds=30)
                    if observed_at is None
                    else observed_at + self.max_active_age
                ),
                observed_at=now if observed_at is None else observed_at,
            ))
        return tuple(result)

    def placements(self) -> tuple[PlacementObservation, ...]:
        now = datetime.now(timezone.utc)
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            required = {
                "platform_module_lifecycle",
                "platform_module_policy",
                "platform_module_operation_request",
                "platform_module_operation_attempt",
            }
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                if row[0] in required
            }
            if tables != required:
                return ()
            rows = db.execute(
                """SELECT request.module_id,request.component_id,
                          request.host_identity,policy.placement_mode,
                          attempt.occurred_at
                   FROM platform_module_operation_request AS request
                   JOIN platform_module_lifecycle AS lifecycle
                     ON lifecycle.module_id=request.module_id
                    AND lifecycle.package_digest=request.package_digest
                    AND lifecycle.lifecycle='active'
                   JOIN platform_module_policy AS policy
                     ON policy.module_id=request.module_id
                    AND policy.package_digest=request.package_digest
                   JOIN platform_module_operation_attempt AS attempt
                     ON attempt.event_id=(
                       SELECT newest.event_id
                       FROM platform_module_operation_attempt AS newest
                       WHERE newest.request_id=request.request_id
                       ORDER BY newest.event_id DESC LIMIT 1)
                   WHERE request.operation IN ('activate','resume')
                     AND attempt.status='externally_verified_success'
                   ORDER BY attempt.occurred_at DESC,request.request_id DESC"""
            ).fetchall()
        result: dict[tuple[str, str], PlacementObservation] = {}
        for row in rows:
            observed_at = datetime.fromisoformat(
                str(row["occurred_at"])
            ).astimezone(timezone.utc)
            if not -timedelta(seconds=5) <= now - observed_at <= self.max_active_age:
                continue
            key = (str(row["module_id"]), str(row["component_id"]))
            if key in result:
                continue
            result[key] = PlacementObservation(
                module_id=key[0],
                component=key[1],
                host_identity=str(row["host_identity"]),
                placement_mode=PlacementMode(
                    str(row["placement_mode"]).casefold()
                ),
                eligible_hosts=(),
                device_affinity=None,
                observed_at=observed_at,
            )
        return tuple(result[key] for key in sorted(result))

    @staticmethod
    def _outcome_status_map():
        return {
            "denied": (
                OutcomeStatus.DENIED,
                "canonical-authorization",
                "authorization_denied",
            ),
            "cancelled_before_dispatch": (
                OutcomeStatus.CANCELLED,
                "canonical-run-cancellation",
                "cancelled_before_dispatch",
            ),
            "failed_before_external_effect": (
                OutcomeStatus.FAILED,
                "canonical-run-pre-dispatch",
                "failed_before_external_effect",
            ),
            "outcome_unknown": (
                OutcomeStatus.OUTCOME_UNKNOWN,
                None,
                "external_outcome_unknown",
            ),
            "externally_verified_success": (
                OutcomeStatus.SUCCEEDED_VERIFIED,
                "authenticated-adapter-probe",
                None,
            ),
            "externally_verified_failure": (
                OutcomeStatus.FAILED,
                "authenticated-adapter-probe",
                "externally_verified_failure",
            ),
        }

    @staticmethod
    def _outcome_from_row(row, status_map) -> OutcomeObservation:
        status, verification_method, error_class = status_map[str(row["status"])]
        return OutcomeObservation(
            request_id=str(row["request_id"]),
            module_id=str(row["module_id"]),
            capability=f"module.{row['operation']}",
            status=status,
            verification_method=verification_method,
            error_class=error_class,
            settled_at=datetime.fromisoformat(
                str(row["occurred_at"])
            ).astimezone(timezone.utc),
        )

    def outcomes(self) -> tuple[OutcomeObservation, ...]:
        # These are historical, settled RUN observations. They never become
        # current authorization evidence and an attempted effect is omitted
        # unless RUN reached one of the explicit terminal outcomes below.
        status_map = self._outcome_status_map()
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name IN ('platform_module_operation_request',"
                    "'platform_module_operation_attempt')"
                )
            }
            if len(tables) != 2:
                return ()
            rows = db.execute(
                """SELECT request.request_id,request.module_id,
                          request.operation,attempt.status,
                          attempt.occurred_at
                   FROM platform_module_operation_request AS request
                   JOIN platform_module_operation_attempt AS attempt
                     ON attempt.event_id=(
                       SELECT newest.event_id
                       FROM platform_module_operation_attempt AS newest
                       WHERE newest.request_id=request.request_id
                       ORDER BY newest.event_id DESC LIMIT 1)
                   ORDER BY attempt.occurred_at DESC,request.request_id DESC
                   LIMIT ?""",
                (_OUTCOME_LIMIT,),
            ).fetchall()
        result = []
        for row in rows:
            mapped = status_map.get(str(row["status"]))
            if mapped is None:
                continue
            result.append(self._outcome_from_row(row, status_map))
        return tuple(result)

    def outcome_page(
        self, *, after_cursor: str | None, limit: int,
    ) -> OutcomePage:
        """Read terminal outcomes in durable journal order without starvation."""
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("outcome page limit must be in 1..128")
        if after_cursor is None:
            after_event_id = 0
        else:
            if not isinstance(after_cursor, str) or not after_cursor.startswith(
                _OUTCOME_CURSOR_PREFIX
            ):
                raise ValueError("module outcome cursor is incompatible")
            suffix = after_cursor.removeprefix(_OUTCOME_CURSOR_PREFIX)
            if not suffix.isdigit():
                raise ValueError("module outcome cursor is invalid")
            after_event_id = int(suffix)
        status_map = self._outcome_status_map()
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND "
                    "name IN ('platform_module_operation_request',"
                    "'platform_module_operation_attempt')"
                )
            }
            if len(tables) != 2:
                return OutcomePage((), after_cursor, False)
            terminal = tuple(status_map)
            placeholders = ",".join("?" for _ in terminal)
            rows = db.execute(
                f"""SELECT attempt.event_id,request.request_id,
                            request.module_id,request.operation,attempt.status,
                            attempt.occurred_at
                     FROM platform_module_operation_attempt AS attempt
                     JOIN platform_module_operation_request AS request
                       ON request.request_id=attempt.request_id
                     WHERE attempt.event_id>?
                       AND attempt.status IN ({placeholders})
                       AND attempt.event_id=(
                         SELECT newest.event_id
                         FROM platform_module_operation_attempt AS newest
                         WHERE newest.request_id=request.request_id
                         ORDER BY newest.event_id DESC LIMIT 1)
                     ORDER BY attempt.event_id
                     LIMIT ?""",
                (after_event_id, *terminal, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        selected = rows[:limit]
        outcomes = tuple(
            self._outcome_from_row(row, status_map) for row in selected
        )
        next_cursor = (
            after_cursor
            if not selected
            else _OUTCOME_CURSOR_PREFIX + str(selected[-1]["event_id"])
        )
        return OutcomePage(outcomes, next_cursor, has_more)
