"""Bounded provenance reporting for a typed environment snapshot."""
from .model import EnvironmentSnapshot


def environment_sources(snapshot: EnvironmentSnapshot) -> str:
    sources = [
        "Environment context sources:",
        "- Clock: trusted runtime host clock.",
    ]
    configured = snapshot.configured_location
    if configured is None:
        sources.append("- Configured location: unavailable.")
    else:
        sources.append(
            "- Configured location: "
            f"{configured.label} ({configured.subject.value}) "
            f"from {configured.source_id}; configuration is not "
            "current physical-location proof."
        )

    host = snapshot.host_location
    if host is None:
        sources.append("- Configured runtime host location: unavailable.")
    else:
        sources.append(
            "- Configured runtime host location: "
            f"{host.label}; timezone={host.timezone}; "
            f"source={host.source_id}; configuration is not "
            "current physical-location proof."
        )

    current = snapshot.current_location
    if current is None:
        sources.append(
            "- Current physical location evidence: unavailable."
        )
    else:
        sources.append(
            "- Current physical location evidence: "
            f"{current.source_id} "
            f"({snapshot.current_location_freshness.value}, "
            f"subject={current.subject.value})."
        )

    if snapshot.timezone is None:
        sources.append("- Environment timezone: unavailable.")
    else:
        sources.append(
            "- Environment timezone: "
            f"{snapshot.timezone}, derived from the effective "
            "location evidence."
        )

    if snapshot.season is None:
        sources.append("- Season: unavailable.")
    else:
        sources.append(
            "- Season: derived from the effective location and date."
        )

    if snapshot.daylight is None:
        sources.append("- Daylight/sunrise/sunset: unavailable.")
    else:
        sources.append(
            "- Daylight/sunrise/sunset: derived from the effective "
            "location, date, and timezone."
        )

    weather = snapshot.weather
    if weather is None:
        sources.append("- Weather/forecast evidence: unavailable.")
    else:
        sources.append(
            "- Weather/forecast evidence: "
            f"{weather.source_id} "
            f"({snapshot.weather_freshness.value})."
        )

    indoor = snapshot.indoor
    if indoor is None:
        sources.append("- Indoor environment evidence: unavailable.")
    else:
        sources.append(
            "- Indoor environment evidence: "
            f"{indoor.source_id} "
            f"({snapshot.indoor_freshness.value})."
        )

    if snapshot.provider_errors:
        sources.append(
            "- Provider status: degraded evidence is present; "
            "provider error details are intentionally bounded."
        )

    sources.append(
        "Coordinates and provider credentials are not exposed in "
        "this report."
    )
    return "\n".join(sources)
