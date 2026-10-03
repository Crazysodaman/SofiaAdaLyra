"""Persistent environment settings for Sofía's canonical runtime."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from sofia.config.defaults import production_state_path
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.environment.model import LocationSubject


def _state_path(raw: str | None) -> Path:
    return Path(raw) if raw else production_state_path()


def _subject(value: str) -> LocationSubject:
    try:
        return LocationSubject(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "subject must be user, site, or host"
        ) from exc


def _show(settings: RuntimeUserSettings) -> None:
    print(f"location_label={settings.location_label or ''}")
    print(f"location_timezone={settings.location_timezone or ''}")
    print(
        "location_latitude="
        + (
            ""
            if settings.location_latitude is None
            else str(settings.location_latitude)
        )
    )
    print(
        "location_longitude="
        + (
            ""
            if settings.location_longitude is None
            else str(settings.location_longitude)
        )
    )
    print(f"location_subject={settings.location_subject.value}")
    print(f"nws_enabled={str(settings.nws_enabled).lower()}")
    print(f"nws_location_subject={settings.nws_location_subject.value}")
    print(f"weather_max_age_seconds={settings.weather_max_age_seconds}")


def configure(
    *,
    state_path: Path,
    label: str,
    timezone_name: str,
    latitude: float | None,
    longitude: float | None,
    subject: LocationSubject,
    enable_nws: bool | None,
) -> RuntimeUserSettings:
    if (latitude is None) != (longitude is None):
        raise ValueError("latitude and longitude must be supplied together")
    store = RuntimeUserSettingsStore(state_path)
    current = store.load()
    updated = replace(
        current,
        location_label=label,
        location_timezone=timezone_name,
        location_latitude=latitude,
        location_longitude=longitude,
        location_subject=subject,
        nws_enabled=(
            current.nws_enabled
            if enable_nws is None
            else enable_nws
        ),
        nws_location_subject=subject,
    )
    store.save(updated)
    return updated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.environment.settings_cli"
    )
    parser.add_argument("--state-path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show")

    set_location = sub.add_parser("set-location")
    set_location.add_argument("--label", default="Home")
    set_location.add_argument(
        "--timezone",
        default="America/Chicago",
    )
    set_location.add_argument("--latitude", type=float)
    set_location.add_argument("--longitude", type=float)
    set_location.add_argument(
        "--subject",
        type=_subject,
        default=LocationSubject.USER,
    )
    nws_group = set_location.add_mutually_exclusive_group()
    nws_group.add_argument(
        "--enable-nws",
        dest="enable_nws",
        action="store_true",
    )
    nws_group.add_argument(
        "--disable-nws",
        dest="enable_nws",
        action="store_false",
    )
    set_location.set_defaults(enable_nws=None)

    central = sub.add_parser("central-time")
    central.add_argument("--label", default="Home")

    args = parser.parse_args(argv)
    path = _state_path(args.state_path)
    try:
        store = RuntimeUserSettingsStore(path)
        if args.command == "show":
            _show(store.load())
            return 0
        if args.command == "central-time":
            current = store.load()
            updated = replace(
                current,
                location_label=args.label,
                location_timezone="America/Chicago",
            )
            store.save(updated)
            _show(updated)
            return 0
        updated = configure(
            state_path=path,
            label=args.label,
            timezone_name=args.timezone,
            latitude=args.latitude,
            longitude=args.longitude,
            subject=args.subject,
            enable_nws=args.enable_nws,
        )
        _show(updated)
        return 0
    except Exception as exc:
        print(
            f"environment settings failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
