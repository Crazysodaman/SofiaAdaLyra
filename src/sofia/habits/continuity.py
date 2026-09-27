from __future__ import annotations

from datetime import datetime, timezone

from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.environment.model import EnvironmentSnapshot, EnvironmentFreshness
from sofia.habits.engine import HabitPatternEngine
from sofia.habits.model import ObservationCoverage, SourceQuality
from sofia.habits.pattern_store import HabitPatternStore
from sofia.habits.patterns import CadenceKind, HabitCategory
from sofia.habits.recorder import HabitObservationRecorder
from sofia.habits.store import HabitObservationStore
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
            context = {
                key: value
                for key, value in observation.context.items()
                if key in {"daypart", "day_type"}
            }
            pattern = self.engine.observe_support(
                observation,
                category=HabitCategory.CONVERSATION_ROUTINE,
                cadence=CadenceKind.DAILY,
                pattern_context=context,
                now=current,
            )
            if pattern is not None:
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
