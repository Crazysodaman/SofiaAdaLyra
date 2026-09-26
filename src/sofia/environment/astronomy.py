"""Deterministic season and approximate solar-daylight derivation.

No network, geocoding, locale inference or model judgment occurs here.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo

from .model import (
    DaylightObservation,
    DaylightState,
    Season,
)


def season_for(*, day: date, latitude: float) -> Season:
    """Return an approximate astronomical season for a known hemisphere."""
    if not isinstance(day, date):
        raise TypeError("day must be a date")
    if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
        raise TypeError("latitude must be numeric")
    lat = float(latitude)
    if not -90.0 <= lat <= 90.0:
        raise ValueError("latitude must be between -90 and 90")

    month_day = (day.month, day.day)
    if month_day >= (12, 21) or month_day < (3, 20):
        northern = Season.WINTER
    elif month_day < (6, 20):
        northern = Season.SPRING
    elif month_day < (9, 22):
        northern = Season.SUMMER
    else:
        northern = Season.AUTUMN

    if lat >= 0:
        return northern

    opposite = {
        Season.WINTER: Season.SUMMER,
        Season.SPRING: Season.AUTUMN,
        Season.SUMMER: Season.WINTER,
        Season.AUTUMN: Season.SPRING,
    }
    return opposite[northern]


def _solar_minutes_utc(
    *,
    day: date,
    latitude: float,
    longitude: float,
) -> tuple[float | None, float | None, DaylightState | None]:
    """NOAA-style sunrise/sunset approximation in minutes from 00:00 UTC."""
    day_number = day.timetuple().tm_yday
    gamma = 2.0 * math.pi / 365.0 * (day_number - 1)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )
    latitude_radians = math.radians(latitude)
    zenith = math.radians(90.833)
    denominator = math.cos(latitude_radians) * math.cos(declination)
    if abs(denominator) < 1e-12:
        cosine_hour_angle = math.inf
    else:
        cosine_hour_angle = (
            math.cos(zenith)
            / denominator
            - math.tan(latitude_radians) * math.tan(declination)
        )

    if cosine_hour_angle > 1.0:
        return None, None, DaylightState.POLAR_NIGHT
    if cosine_hour_angle < -1.0:
        return None, None, DaylightState.POLAR_DAY

    hour_angle_degrees = math.degrees(math.acos(cosine_hour_angle))
    solar_noon_utc = 720.0 - (4.0 * longitude) - equation_of_time
    sunrise_utc = solar_noon_utc - (4.0 * hour_angle_degrees)
    sunset_utc = solar_noon_utc + (4.0 * hour_angle_degrees)
    return sunrise_utc, sunset_utc, None


def daylight_for(
    *,
    now: datetime,
    latitude: float,
    longitude: float,
    timezone_name: str,
) -> DaylightObservation:
    """Derive daylight state and approximate sunrise/sunset for a known place."""
    if (
        not isinstance(now, datetime)
        or now.tzinfo is None
        or now.utcoffset() is None
    ):
        raise ValueError("now must be timezone-aware")
    if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
        raise TypeError("latitude must be numeric")
    if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
        raise TypeError("longitude must be numeric")
    lat = float(latitude)
    lon = float(longitude)
    if not -90.0 <= lat <= 90.0:
        raise ValueError("latitude must be between -90 and 90")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("longitude must be between -180 and 180")

    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone)
    local_day = local_now.date()
    sunrise_minutes, sunset_minutes, polar = _solar_minutes_utc(
        day=local_day,
        latitude=lat,
        longitude=lon,
    )

    if polar is not None:
        return DaylightObservation(state=polar)

    assert sunrise_minutes is not None
    assert sunset_minutes is not None

    utc_midnight = datetime.combine(
        local_day,
        time.min,
        tzinfo=timezone.utc,
    )
    sunrise_utc = utc_midnight + timedelta(minutes=sunrise_minutes)
    sunset_utc = utc_midnight + timedelta(minutes=sunset_minutes)
    sunrise_local = sunrise_utc.astimezone(zone)
    sunset_local = sunset_utc.astimezone(zone)

    current_utc = now.astimezone(timezone.utc)
    # Solar events derived from the local calendar date can land on an adjacent
    # UTC date. Compare the actual instants rather than local clock strings.
    state = (
        DaylightState.DAY
        if sunrise_utc <= current_utc < sunset_utc
        else DaylightState.NIGHT
    )
    return DaylightObservation(
        state=state,
        sunrise=sunrise_local,
        sunset=sunset_local,
    )
