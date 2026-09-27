"""Application-facing habit learning coordinator."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sofia.environment.service import EnvironmentService
from sofia.social.model import PrincipalContext

from .context import habit_context_from_environment
from .detector import HabitPatternDetector
from .expectation import HabitExpectationEngine
from .model import (
    CoverageState,
    HabitObservation,
    ObservationCoverage,
    ObservationSource,
)
from .store import HabitStore


class HabitLearningService:
    """Record source-backed observations and update descriptive patterns."""

    def __init__(
        self,
        *,
        state_path,
        environment_service: EnvironmentService,
    ) -> None:
        if not isinstance(environment_service, EnvironmentService):
            raise TypeError("environment_service must be EnvironmentService")
        self.store = HabitStore(state_path)
        self.environment = environment_service
        self.detector = HabitPatternDetector(self.store)
        self.expectations = HabitExpectationEngine(self.store)

    def record_conversation_contact(
        self,
        *,
        principal: PrincipalContext,
        message_id: str,
        occurred_at: datetime,
    ) -> HabitObservation:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext")
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id required")
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")

        snapshot = self.environment.snapshot(
            now=occurred_at,
            refresh_providers=True,
        )
        item = HabitObservation.create(
            observation_id=f"habit:conversation:{message_id}",
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            kind="conversation.contact",
            value="contact",
            observed_at=occurred_at.astimezone(timezone.utc),
            source_id=message_id,
            source=ObservationSource.OBSERVED,
            context=habit_context_from_environment(snapshot),
        )
        self.store.record_observation(item)
        self.detector.analyze(
            principal_id=principal.principal_id,
            now=occurred_at,
        )
        timezone_name = snapshot.timezone
        self.expectations.ensure_time_expectations(
            principal_id=principal.principal_id,
            timezone_name=timezone_name,
            now=occurred_at,
        )
        return item

    def record_running_coverage(
        self,
        *,
        principal_id: str,
        started_at: datetime,
        ended_at: datetime,
        source_id: str = "application-background",
        kind: str = "conversation.contact",
        max_gap: timedelta = timedelta(minutes=5),
    ) -> ObservationCoverage | None:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id required")
        if (
            started_at.tzinfo is None
            or started_at.utcoffset() is None
            or ended_at.tzinfo is None
            or ended_at.utcoffset() is None
        ):
            raise ValueError("coverage timestamps must be timezone-aware")
        start = started_at.astimezone(timezone.utc)
        end = ended_at.astimezone(timezone.utc)
        if end <= start:
            return None
        if end - start > max_gap:
            # A long scheduler/process gap is not evidence of continuous
            # observation. Leave it uncovered instead of inventing uptime.
            return None
        raw = f"{principal_id}\x1f{kind}\x1f{start.isoformat()}\x1f{end.isoformat()}"
        item = ObservationCoverage(
            coverage_id="habit-coverage:" + sha256(raw.encode("utf-8")).hexdigest()[:32],
            principal_id=principal_id,
            source_id=source_id,
            kind=kind,
            started_at=start,
            ended_at=end,
            state=CoverageState.COVERED,
        )
        self.store.record_coverage(item)
        return item

    def record_observation(
        self,
        item: HabitObservation,
        *,
        analyze: bool = True,
    ) -> bool:
        if not isinstance(item, HabitObservation):
            raise TypeError("HabitObservation required")
        if type(analyze) is not bool:
            raise TypeError("analyze must be bool")
        created = self.store.record_observation(item)
        if analyze:
            self.detector.analyze(
                principal_id=item.principal_id,
                now=item.observed_at,
            )
        return created

    def evaluate(
        self,
        *,
        principal_id: str,
        now: datetime,
    ):
        return self.expectations.evaluate_pending(
            principal_id=principal_id,
            now=now,
        )
