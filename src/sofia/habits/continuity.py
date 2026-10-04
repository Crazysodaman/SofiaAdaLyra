from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.environment.model import EnvironmentSnapshot, EnvironmentFreshness
from sofia.habits.engine import HabitPatternEngine
from sofia.habits.expectations import (
    ExpectationStatus,
    HabitExpectationEngine,
    HabitExpectationStore,
)
from sofia.habits.model import ObservationCoverage, SourceQuality
from sofia.habits.pattern_store import HabitPatternStore
from sofia.habits.patterns import CadenceKind, HabitCategory
from sofia.habits.store import HabitObservationRecorder, HabitObservationStore
from sofia.social.model import PrincipalContext
from sofia.state.plane import StatePlane


def _daypart(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


class HabitContinuityCoordinator:
    """Production HABIT glue over conversation/environment evidence."""

    def __init__(self, state_plane: StatePlane) -> None:
        if not isinstance(state_plane, StatePlane):
            raise TypeError("state_plane must be StatePlane")
        self.observations = HabitObservationStore(state_plane)
        self.recorder = HabitObservationRecorder(self.observations)
        self.patterns = HabitPatternStore(state_plane)
        self.engine = HabitPatternEngine(self.patterns)
        self.expectations = HabitExpectationStore(state_plane)
        self.expectation_engine = HabitExpectationEngine(self.expectations)

    def observe_conversation(
        self,
        *,
        message: ConversationMessage,
        principal: PrincipalContext | None,
        environment: EnvironmentSnapshot,
    ):
        if not isinstance(message, ConversationMessage):
            raise TypeError("message must be ConversationMessage")
        if message.role is not ConversationRole.USER:
            return None
        if principal is None:
            return None
        if not isinstance(principal, PrincipalContext):
            raise TypeError("principal must be PrincipalContext or None")
        if not isinstance(environment, EnvironmentSnapshot):
            raise TypeError("environment must be EnvironmentSnapshot")
        if environment.user_local_time is None or environment.timezone is None:
            return None

        local = environment.user_local_time
        context = {
            "daypart": _daypart(local.hour),
            "weekday": local.strftime("%A").casefold(),
            "day_type": "weekend" if local.weekday() >= 5 else "weekday",
        }
        if environment.season is not None:
            context["season"] = environment.season.value
        if environment.daylight is not None:
            context["daylight"] = environment.daylight.state.value
        if (
            environment.weather is not None
            and environment.weather_freshness is EnvironmentFreshness.CURRENT
        ):
            context["weather"] = environment.weather.condition

        return self.recorder.record(
            principal_id=principal.principal_id,
            audience_id=principal.audience_id,
            kind="conversation.user_message",
            occurred_at=message.created_at,
            local_timestamp=local,
            timezone_name=environment.timezone,
            context=context,
            evidence_ref=message.id,
            source_quality=SourceQuality.VERIFIED,
            coverage=ObservationCoverage.OBSERVED,
        )

    def record_runtime_coverage(
        self,
        *,
        principal_id: str,
        audience_id: str,
        started_at: datetime,
        ended_at: datetime,
    ):
        return self.recorder.record_coverage(
            principal_id=principal_id,
            audience_id=audience_id,
            source_id="sofia-runtime",
            started_at=started_at,
            ended_at=ended_at,
            status=ObservationCoverage.OBSERVED,
            quality=SourceQuality.VERIFIED,
            reason="application background loop alive",
        )

    def analyze_conversation_patterns(
        self,
        *,
        principal_id: str,
        audience_id: str,
        now: datetime,
    ) -> int:
        current = now.astimezone(timezone.utc)
        count = 0
        for observation in self.observations.observations(
            principal_id=principal_id,
            audience_id=audience_id,
        ):
            if observation.kind != "conversation.user_message":
                continue
            daily_context = {
                key: value
                for key, value in observation.context.items()
                if key in {"daypart", "day_type"}
            }
            pattern = self.engine.observe_support(
                observation,
                category=HabitCategory.CONVERSATION_ROUTINE,
                cadence=CadenceKind.DAILY,
                pattern_context=daily_context,
                now=current,
            )
            if pattern is not None:
                count += 1

            # Season is recorded as a separate cadence rather than folded into
            # the daily signature. This lets repeated evidence support a real
            # seasonal pattern without weakening or fragmenting the established
            # daypart/day-type routine.
            season = observation.context.get("season")
            daypart = observation.context.get("daypart")
            if season and daypart:
                seasonal = self.engine.observe_support(
                    observation,
                    category=HabitCategory.CONVERSATION_ROUTINE,
                    cadence=CadenceKind.SEASONAL,
                    pattern_context={
                        "season": season,
                        "daypart": daypart,
                    },
                    now=current,
                )
                if seasonal is not None:
                    count += 1

            # Ambient observations are correlations, never routine truth.
            # Weather is already freshness-gated when the observation is
            # recorded. Daylight is deterministic environment evidence.
            weather = observation.context.get("weather")
            daylight = observation.context.get("daylight")
            for key, value in (
                ("weather", weather),
                ("daylight", daylight),
            ):
                if not value:
                    continue
                correlation_context = {
                    key: value,
                }
                if daypart:
                    correlation_context["daypart"] = daypart
                correlated = self.engine.observe_support(
                    observation,
                    category=HabitCategory.ENVIRONMENT_CORRELATION,
                    cadence=CadenceKind.TIME_OF_DAY,
                    pattern_context=correlation_context,
                    now=current,
                )
                if correlated is not None:
                    count += 1
        return count

    def decay_patterns(
        self,
        *,
        principal_id: str,
        audience_id: str,
        now: datetime,
    ) -> int:
        count = 0
        for pattern in self.patterns.patterns(
            principal_id=principal_id,
            audience_id=audience_id,
        ):
            self.engine.decay(pattern, now=now)
            count += 1
        return count


    @staticmethod
    def _daypart_window(local_now: datetime, daypart: str) -> tuple[datetime, datetime]:
        if daypart == "morning":
            start_hour, end_hour = 5, 12
        elif daypart == "afternoon":
            start_hour, end_hour = 12, 17
        elif daypart == "evening":
            start_hour, end_hour = 17, 22
        else:
            start_hour, end_hour = 22, 29
        base = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = base + timedelta(hours=start_hour)
        end = base + timedelta(hours=end_hour)
        if end <= local_now:
            start += timedelta(days=1)
            end += timedelta(days=1)
        return start, end

    def evaluate_expectations(
        self,
        *,
        principal_id: str,
        audience_id: str,
        now: datetime,
    ) -> int:
        current = now.astimezone(timezone.utc)
        observations = self.observations.observations(
            principal_id=principal_id,
            audience_id=audience_id,
        )
        if not observations:
            return 0

        timezone_name = observations[-1].timezone
        local_now = current.astimezone(ZoneInfo(timezone_name))
        changed = 0

        existing = self.expectations.list(
            principal_id=principal_id,
            audience_id=audience_id,
        )
        pending_by_pattern = {
            item.pattern_id: item
            for item in existing
            if item.status is ExpectationStatus.PENDING
        }

        for expectation in existing:
            if expectation.status is not ExpectationStatus.PENDING:
                continue
            if current < expectation.window_end_utc:
                continue
            matching = [
                observation
                for observation in observations
                if (
                    expectation.window_start_utc
                    <= observation.occurred_at_utc
                    <= expectation.window_end_utc
                )
            ]
            if matching:
                self.expectation_engine.resolve(
                    expectation,
                    status=ExpectationStatus.FULFILLED,
                    resolved_at=current,
                    evidence_ref=matching[-1].evidence_ref,
                )
            else:
                coverage = tuple(
                    window
                    for window in self.observations.coverage_windows(
                        principal_id=principal_id,
                        audience_id=audience_id,
                    )
                    if window.status in (
                        ObservationCoverage.OBSERVED,
                        ObservationCoverage.PARTIAL,
                    )
                    and window.ended_at_utc >= expectation.window_start_utc
                    and window.started_at_utc <= expectation.window_end_utc
                )
                cursor = expectation.window_start_utc
                coverage_evidence = None
                for window in sorted(
                    coverage,
                    key=lambda item: (
                        item.started_at_utc,
                        item.ended_at_utc,
                    ),
                ):
                    if window.started_at_utc > cursor:
                        break
                    if window.ended_at_utc > cursor:
                        cursor = window.ended_at_utc
                        coverage_evidence = window.coverage_id
                    if cursor >= expectation.window_end_utc:
                        break
                covered = cursor >= expectation.window_end_utc
                self.expectation_engine.resolve(
                    expectation,
                    status=(
                        ExpectationStatus.MISSED
                        if covered
                        else ExpectationStatus.UNOBSERVABLE
                    ),
                    resolved_at=current,
                    evidence_ref=coverage_evidence if covered else None,
                )
            changed += 1

        for pattern in self.patterns.patterns(
            principal_id=principal_id,
            audience_id=audience_id,
        ):
            if pattern.lifecycle.value not in ("established", "trusted"):
                continue
            if pattern.pattern_id in pending_by_pattern:
                continue
            daypart = pattern.context.get("daypart")
            if not daypart:
                continue
            local_start, local_end = self._daypart_window(
                local_now,
                daypart,
            )
            self.expectation_engine.create(
                pattern=pattern,
                window_start_utc=local_start.astimezone(timezone.utc),
                window_end_utc=local_end.astimezone(timezone.utc),
                local_window_start=local_start,
                local_window_end=local_end,
                timezone_name=timezone_name,
                created_at=current,
            )
            changed += 1
        return changed
