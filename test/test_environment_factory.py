from pathlib import Path

import pytest

from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.environment.config import EnvironmentConfiguration
from sofia.environment.factory import (
    HOME_ASSISTANT_ENVIRONMENT_CAPABILITY,
    create_environment_service,
)
from sofia.environment.home_assistant import HomeAssistantEnvironmentProvider


def configuration(environment, *, capabilities=()):
    return SofiaConfiguration(
        constitution_path=Path("constitution.md"),
        constitution_hash_path=Path("constitution.sha256"),
        identity_path=Path("identity.json"),
        personality_path=Path("personality.json"),
        avatar_path=Path("avatar.json"),
        state_path=Path("sofia.db"),
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=Path("."),
        standing_allowed_capabilities=capabilities,
        environment=environment,
    )


def test_factory_has_no_provider_when_environment_sources_are_unconfigured(
    monkeypatch,
):
    monkeypatch.delenv("SOFIA_HOME_ASSISTANT_URL", raising=False)
    monkeypatch.delenv("SOFIA_HOME_ASSISTANT_TOKEN", raising=False)
    service = create_environment_service(
        configuration(EnvironmentConfiguration())
    )
    assert service.providers == ()


def test_factory_requires_ha_credentials_when_ha_entities_are_enabled(
    monkeypatch,
):
    monkeypatch.delenv("SOFIA_HOME_ASSISTANT_URL", raising=False)
    monkeypatch.delenv("SOFIA_HOME_ASSISTANT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="URL/TOKEN"):
        create_environment_service(
            configuration(
                EnvironmentConfiguration(
                    home_assistant_weather_entity="weather.home",
                ),
                capabilities=(
                    HOME_ASSISTANT_ENVIRONMENT_CAPABILITY,
                ),
            )
        )


def test_factory_attaches_ha_provider_without_contacting_network(
    monkeypatch,
):
    monkeypatch.setenv(
        "SOFIA_HOME_ASSISTANT_URL",
        "http://home-assistant.invalid",
    )
    monkeypatch.setenv(
        "SOFIA_HOME_ASSISTANT_TOKEN",
        "test-only-token",
    )
    service = create_environment_service(
        configuration(
            EnvironmentConfiguration(
                home_assistant_weather_entity="weather.home",
            ),
            capabilities=(
                HOME_ASSISTANT_ENVIRONMENT_CAPABILITY,
            ),
        )
    )
    assert len(service.providers) == 1
    assert isinstance(
        service.providers[0],
        HomeAssistantEnvironmentProvider,
    )


def test_factory_rejects_ha_environment_without_explicit_standing_grant(
    monkeypatch,
):
    monkeypatch.setenv(
        "SOFIA_HOME_ASSISTANT_URL",
        "http://home-assistant.invalid",
    )
    monkeypatch.setenv(
        "SOFIA_HOME_ASSISTANT_TOKEN",
        "test-only-token",
    )
    with pytest.raises(PermissionError, match="environment.home_assistant.read"):
        create_environment_service(
            configuration(
                EnvironmentConfiguration(
                    home_assistant_weather_entity="weather.home",
                )
            )
        )

