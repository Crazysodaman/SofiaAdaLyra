"""Build habit context from trusted ENVIRONMENT snapshots."""
from __future__ import annotations

from datetime import datetime

from sofia.environment.model import EnvironmentFreshness, EnvironmentSnapshot


def habit_context_from_environment(
    snapshot: EnvironmentSnapshot,
) -> dict[str, str]:
    """Return bounded correlation context without asserting causality.

    User-local weekday/hour are included only when ENVIRONMENT has an explicit
    user/site timezone. Host-local time is never silently substituted for it.
    Weather is included only while current.
    """
    if not isinstance(snapshot, EnvironmentSnapshot):
        raise TypeError("EnvironmentSnapshot required")

    context: dict[str, str] = {}
    local = snapshot.user_local_time
    if local is not None and snapshot.timezone is not None:
        context["weekday"] = str(local.weekday())
        context["hour_bucket"] = str(local.hour // 2)
        context["day_of_month"] = str(local.day)
        context["month"] = str(local.month)
        context["month_day"] = f"{local.month:02d}-{local.day:02d}"

    if snapshot.season is not None:
        context["season"] = snapshot.season.value

    if snapshot.daylight is not None:
        context["daylight"] = snapshot.daylight.state.value

    if (
        snapshot.weather is not None
        and snapshot.weather_freshness is EnvironmentFreshness.CURRENT
    ):
        condition = " ".join(snapshot.weather.condition.casefold().split())
        if condition:
            context["weather"] = condition[:120]

    location = snapshot.effective_location
    if location is not None:
        context["location_label"] = location.label[:120]

    return context
