"""Regression tests for configuration/runtime import-cycle boundaries."""


def test_configuration_can_import_before_environment_service():
    from sofia.config.model import SofiaConfiguration
    from sofia.environment import EnvironmentService

    assert SofiaConfiguration is not None
    assert EnvironmentService is not None


def test_environment_configuration_can_import_without_runtime_bootstrap():
    from sofia.environment.config import EnvironmentConfiguration

    assert EnvironmentConfiguration().location is None
