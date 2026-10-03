from pathlib import Path

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.environment.model import LocationSubject
from sofia.environment.settings_cli import configure, main


def test_configure_persists_weather_location_and_nws(tmp_path):
    state = tmp_path / "sofia.db"

    settings = configure(
        state_path=state,
        label="Home",
        timezone_name="America/Chicago",
        latitude=32.5,
        longitude=-97.1,
        subject=LocationSubject.USER,
        enable_nws=True,
    )

    reloaded = RuntimeUserSettingsStore(state).load()
    assert settings == reloaded
    assert reloaded.location_label == "Home"
    assert reloaded.location_timezone == "America/Chicago"
    assert reloaded.location_latitude == 32.5
    assert reloaded.location_longitude == -97.1
    assert reloaded.nws_enabled is True


def test_central_time_command_preserves_other_settings(tmp_path):
    state = tmp_path / "sofia.db"
    store = RuntimeUserSettingsStore(state)
    original = store.load()
    assert original.location_timezone == "America/Chicago"

    code = main(
        [
            "--state-path",
            str(state),
            "central-time",
            "--label",
            "Home",
        ]
    )

    assert code == 0
    saved = store.load()
    assert saved.location_timezone == "America/Chicago"
    assert saved.location_label == "Home"


def test_configure_requires_coordinate_pair(tmp_path):
    state = tmp_path / "sofia.db"

    try:
        configure(
            state_path=state,
            label="Home",
            timezone_name="America/Chicago",
            latitude=32.5,
            longitude=None,
            subject=LocationSubject.USER,
            enable_nws=True,
        )
    except ValueError as exc:
        assert "latitude and longitude" in str(exc)
    else:
        raise AssertionError("expected coordinate-pair validation")
