from sofia.config import create_default_configuration
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)
from sofia.environment.model import LocationSubject


def _clear_environment_overrides(monkeypatch):
    names = (
        "SOFIA_ENVIRONMENT_LOCATION_LABEL",
        "SOFIA_ENVIRONMENT_TIMEZONE",
        "SOFIA_ENVIRONMENT_LATITUDE",
        "SOFIA_ENVIRONMENT_LONGITUDE",
        "SOFIA_ENVIRONMENT_LOCATION_SUBJECT",
        "SOFIA_ENVIRONMENT_NWS_ENABLED",
        "SOFIA_ENVIRONMENT_NWS_LOCATION_SUBJECT",
        "SOFIA_ENVIRONMENT_NWS_USER_AGENT",
        "SOFIA_ENVIRONMENT_REFRESH_SECONDS",
        "SOFIA_ENVIRONMENT_WEATHER_MAX_AGE_SECONDS",
        "SOFIA_ENVIRONMENT_INDOOR_MAX_AGE_SECONDS",
        "SOFIA_ENVIRONMENT_CURRENT_LOCATION_MAX_AGE_SECONDS",
        "SOFIA_ENVIRONMENT_HA_WEATHER_ENTITY",
        "SOFIA_ENVIRONMENT_HA_INDOOR_TEMPERATURE_ENTITY",
        "SOFIA_ENVIRONMENT_HA_INDOOR_HUMIDITY_ENTITY",
        "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_ENTITY",
        "SOFIA_ENVIRONMENT_HA_CURRENT_LOCATION_SUBJECT",
        "SOFIA_COGNITION_ROUTING_ENABLED",
        "SOFIA_COGNITION_ROUTING_PROVIDER",
        "SOFIA_COGNITION_PRIMARY_MODEL",
        "SOFIA_COGNITION_SECONDARY_MODEL",
        "SOFIA_COGNITION_PRIMARY_CONTEXT_SIZE",
        "SOFIA_COGNITION_SECONDARY_CONTEXT_SIZE",
        "SOFIA_COGNITION_VERIFY_ENABLED",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_default_configuration_applies_saved_owner_settings(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "state"
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "development")
    _clear_environment_overrides(monkeypatch)

    RuntimeUserSettingsStore(state_root / "sofia.db").save(
        RuntimeUserSettings(
            provider_model="saved-model:latest",
            provider_context_size=32768,
            provider_thinking=True,
            location_label="Home",
            location_timezone="America/Chicago",
            location_latitude=32.5,
            location_longitude=-97.1,
            location_subject=LocationSubject.USER,
            nws_enabled=True,
            nws_location_subject=LocationSubject.USER,
            refresh_seconds=120,
        )
    )

    configuration = create_default_configuration()

    assert configuration.provider.model == "saved-model:latest"
    assert configuration.provider.context_size == 32768
    assert configuration.provider.thinking is True
    assert configuration.environment.location is not None
    assert configuration.environment.location.label == "Home"
    assert configuration.environment.location.timezone == "America/Chicago"
    assert configuration.environment.nws_enabled is True
    assert configuration.environment.refresh_seconds == 120
    assert "environment.nws.read" in (
        configuration.standing_allowed_capabilities
    )


def test_explicit_environment_override_beats_saved_setting(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "state"
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "development")
    _clear_environment_overrides(monkeypatch)

    RuntimeUserSettingsStore(state_root / "sofia.db").save(
        RuntimeUserSettings(nws_enabled=True)
    )
    monkeypatch.setenv("SOFIA_ENVIRONMENT_NWS_ENABLED", "0")

    configuration = create_default_configuration()

    assert configuration.environment.nws_enabled is False



def test_saved_owner_settings_can_enable_cognitive_routing(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "state-routing"
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "development")
    _clear_environment_overrides(monkeypatch)

    RuntimeUserSettingsStore(state_root / "sofia.db").save(
        RuntimeUserSettings(
            cognitive_routing_enabled=True,
            cognitive_primary_model="primary:saved",
            cognitive_secondary_model="secondary:saved",
            cognitive_primary_context_size=12288,
            cognitive_secondary_context_size=6144,
            cognitive_verify_enabled=False,
        )
    )

    configuration = create_default_configuration()

    assert configuration.routing is not None
    assert configuration.routing.enabled is True
    assert configuration.routing.primary is not None
    assert configuration.routing.secondary is not None
    assert configuration.routing.primary.model == "primary:saved"
    assert configuration.routing.secondary.model == "secondary:saved"
    assert configuration.routing.primary.context_size == 12288
    assert configuration.routing.secondary.context_size == 6144
    assert configuration.routing.verify_enabled is False


def test_cognitive_environment_override_beats_saved_routing_setting(
    tmp_path,
    monkeypatch,
):
    state_root = tmp_path / "state-routing-override"
    monkeypatch.setenv("SOFIA_STATE_ROOT", str(state_root))
    monkeypatch.setenv("SOFIA_RUNTIME_MODE", "development")
    _clear_environment_overrides(monkeypatch)

    RuntimeUserSettingsStore(state_root / "sofia.db").save(
        RuntimeUserSettings(
            cognitive_routing_enabled=True,
            cognitive_primary_model="primary:saved",
        )
    )
    monkeypatch.setenv("SOFIA_COGNITION_PRIMARY_MODEL", "primary:env")

    configuration = create_default_configuration()

    assert configuration.routing is not None
    assert configuration.routing.primary is not None
    assert configuration.routing.primary.model == "primary:env"
