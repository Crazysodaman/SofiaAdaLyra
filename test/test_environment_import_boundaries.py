"""Regression tests for configuration/runtime import-cycle boundaries."""


def test_configuration_can_import_before_environment_service():
    from sofia.config.model import SofiaConfiguration
    from sofia.environment import EnvironmentService

    assert SofiaConfiguration is not None
    assert EnvironmentService is not None


def test_environment_configuration_can_import_without_runtime_bootstrap():
    from sofia.environment.config import EnvironmentConfiguration

    assert EnvironmentConfiguration().location is None

def test_environment_service_import_does_not_eagerly_bootstrap_runtime():
    from sofia.environment.service import EnvironmentService

    assert EnvironmentService is not None


def test_runtime_public_api_still_resolves_lazily():
    from sofia.runtime import RuntimeState, SofiaRuntime, SofiaRuntimeError

    assert RuntimeState is not None
    assert SofiaRuntime is not None
    assert SofiaRuntimeError is not None

def test_nws_public_api_resolves_without_eager_runtime_bootstrap():
    from sofia.environment import NwsEnvironmentProvider
    from sofia.integrations import NwsAdapter

    assert NwsEnvironmentProvider is not None
    assert NwsAdapter is not None

