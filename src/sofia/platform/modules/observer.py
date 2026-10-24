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
    PlacementObservation,
    PlatformModuleObserver,
)
from sofia.platform.state.canonical_sqlite import CanonicalSQLiteGuard

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

    def _rows(self) -> tuple[sqlite3.Row, ...]:
        with closing(
            self._guard.connect(timeout=10.0, read_only=True)
        ) as db:
            db.row_factory = sqlite3.Row
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='platform_module_lifecycle'"
            ).fetchone()
            if exists is None:
                return ()
            rows = db.execute(
                "SELECT module_id,version,lifecycle,active_profile,updated_at "
                "FROM platform_module_lifecycle ORDER BY module_id"
            ).fetchall()
        return tuple(rows)

    def described(self) -> tuple[ModuleDescribeObservation, ...]:
        now = datetime.now(timezone.utc)
        return tuple(
            ModuleDescribeObservation(
                module_id=str(row["module_id"]),
                version=str(row["version"]),
                capabilities=(),
                requires_permission=frozenset(),
                active_profile=(
                    "DISABLED" if row["active_profile"] is None
                    else str(row["active_profile"])
                ),
                simulated_only=frozenset(),
                observed_at=now,
            )
            for row in self._rows()
            if str(row["lifecycle"]) in _INSTALLED
        )

    def health(self) -> tuple[ModuleHealthObservation, ...]:
        now = datetime.now(timezone.utc)
        result = []
        for row in self._rows():
            lifecycle = str(row["lifecycle"])
            if lifecycle == ModuleLifecycle.REMOVED.value:
                continue
            updated_at = datetime.fromisoformat(str(row["updated_at"])).astimezone(
                timezone.utc
            )
            fresh_active = (
                lifecycle == ModuleLifecycle.ACTIVE.value
                and -timedelta(seconds=5) <= now - updated_at <= self.max_active_age
            )
            if fresh_active:
                kind = ModuleObservationKind.HEALTHY
                projected_lifecycle = "ACTIVE"
                reasons = ()
            elif lifecycle == ModuleLifecycle.QUARANTINED.value:
                kind = ModuleObservationKind.QUARANTINED
                projected_lifecycle = "QUARANTINED"
                reasons = ("platform-lifecycle-quarantined",)
            else:
                kind = ModuleObservationKind.UNKNOWN_STATE
                projected_lifecycle = lifecycle.upper()
                reasons = (
                    "active-observation-stale"
                    if lifecycle == ModuleLifecycle.ACTIVE.value
                    else f"lifecycle:{lifecycle}",
                )
            result.append(ModuleHealthObservation(
                module_instance_id=str(row["module_id"]),
                host_identity=self.host_identity,
                lifecycle=projected_lifecycle,
                health=kind,
                reason_codes=reasons,
                blocked_dependencies=(),
                fresh_until=now + timedelta(seconds=30),
                observed_at=now,
            ))
        return tuple(result)

    def placements(self) -> tuple[PlacementObservation, ...]:
        return ()

    def outcomes(self) -> tuple[OutcomeObservation, ...]:
        # RUN/effect receipts remain separate historical outcomes and are not
        # converted into current authorization evidence here.
        return ()
