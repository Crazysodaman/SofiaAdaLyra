"""Composition helper for PKG-ENVIRONMENT."""
from __future__ import annotations

import os

from sofia.config.model import SofiaConfiguration
from sofia.integrations.home_assistant import HomeAssistantAdapter

from .home_assistant import HomeAssistantEnvironmentProvider
from .service import EnvironmentService


HOME_ASSISTANT_ENVIRONMENT_CAPABILITY = "environment.home_assistant.read"




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
        base_url = os.environ.get(
            "SOFIA_HOME_ASSISTANT_URL",
            "",
        ).strip()
        token = os.environ.get(
            "SOFIA_HOME_ASSISTANT_TOKEN",
            "",
        ).strip()
        if not base_url or not token:
            raise ValueError(
                "Home Assistant environment entities are configured "
                "but SOFIA_HOME_ASSISTANT_URL/TOKEN are unavailable"
            )
        providers.append(
            HomeAssistantEnvironmentProvider(
                HomeAssistantAdapter(base_url, token),
                environment,
            )
        )

    return EnvironmentService(
        environment,
        providers=tuple(providers),
    )
