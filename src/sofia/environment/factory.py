"""Composition helper for PKG-ENVIRONMENT."""
from __future__ import annotations

import os

from sofia.config.model import SofiaConfiguration
from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.integrations.home_assistant import HomeAssistantAdapter
from sofia.integrations.nws import NwsAdapter
from sofia.safe.secret_store import ProtectedSecretStore

from .home_assistant import HomeAssistantEnvironmentProvider
from .nws import NwsEnvironmentProvider
from .service import EnvironmentService


HOME_ASSISTANT_ENVIRONMENT_CAPABILITY = "environment.home_assistant.read"
NWS_ENVIRONMENT_CAPABILITY = "environment.nws.read"




def create_environment_service(
    configuration: SofiaConfiguration,
) -> EnvironmentService:
    if not isinstance(configuration, SofiaConfiguration):
        raise TypeError(
            "configuration must be SofiaConfiguration"
        )

    environment = configuration.environment
    providers = []

    if environment.home_assistant_enabled:
        if (
            HOME_ASSISTANT_ENVIRONMENT_CAPABILITY
            not in configuration.standing_allowed_capabilities
        ):
            raise PermissionError(
                "Home Assistant environment reads require standing "
                f"capability {HOME_ASSISTANT_ENVIRONMENT_CAPABILITY!r}"
            )
        user_settings = RuntimeUserSettingsStore(
            configuration.state_path
        ).load()
        base_url = (
            os.environ.get(
                "SOFIA_HOME_ASSISTANT_URL",
                "",
            ).strip()
            or (user_settings.home_assistant_url or "")
        )
        token = os.environ.get(
            "SOFIA_HOME_ASSISTANT_TOKEN",
            "",
        ).strip()
        if not token:
            token = (
                ProtectedSecretStore.for_state_path(
                    configuration.state_path
                ).get("home-assistant-token")
                or ""
            )
        if not base_url or not token:
            raise ValueError(
                "Home Assistant environment entities are configured "
                "but Home Assistant URL/TOKEN are unavailable"
            )
        providers.append(
            HomeAssistantEnvironmentProvider(
                HomeAssistantAdapter(base_url, token),
                environment,
            )
        )

    if environment.nws_enabled:
        if (
            NWS_ENVIRONMENT_CAPABILITY
            not in configuration.standing_allowed_capabilities
        ):
            raise PermissionError(
                "NWS environment reads require standing "
                f"capability {NWS_ENVIRONMENT_CAPABILITY!r}"
            )
        providers.append(
            NwsEnvironmentProvider(
                NwsAdapter(environment.nws_user_agent),
                environment,
            )
        )

    return EnvironmentService(
        environment,
        providers=tuple(providers),
    )
