"""Compatibility exports for platform-owned environment configuration.

The environment configuration contracts moved to
``sofia.platform.config.environment`` so Platform configuration does not
import ``sofia.core``.
"""
from sofia.platform.config.environment import (
    ConfiguredLocation,
    EnvironmentConfiguration,
    environment_configuration_from_environ,
)

__all__ = [
    "ConfiguredLocation",
    "EnvironmentConfiguration",
    "environment_configuration_from_environ",
]
