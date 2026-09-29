from sofia.cognition.model_lifecycle import (
    LifecycleManagedCognitiveEngine,
)
from sofia.cognition.routing import RoutingCognitiveEngine
from sofia.composition.root import (
    _create_cognitive_engine,
    _create_model_lifecycle,
)
from sofia.config import create_production_configuration
from sofia.config.user_settings import (
    RuntimeUserSettings,
    RuntimeUserSettingsStore,
)


def test_production_configuration_composes_two_lifecycle_managed_roles(tmp_path):
    state_path=tmp_path/"production"/"sofia.db"
    store=RuntimeUserSettingsStore(state_path)
    store.save(
        RuntimeUserSettings(
            cognitive_routing_enabled=True,
            cognitive_primary_model="owner/primary-production:any",
            cognitive_secondary_model="owner/secondary-production:any",
            cognitive_primary_context_size=16384,
            cognitive_secondary_context_size=8192,
            cognitive_model_auto_manage=True,
            cognitive_model_auto_install=True,
        )
    )

    configuration=create_production_configuration(
        state_path=state_path,
    )
    lifecycle=_create_model_lifecycle(configuration)
    engine=_create_cognitive_engine(
        configuration,
        lifecycle=lifecycle,
    )

    assert isinstance(engine,RoutingCognitiveEngine)
    assert lifecycle is not None
    assert configuration.routing is not None
    assert configuration.routing.primary is not None
    assert configuration.routing.secondary is not None

    primary=engine.registry.primary
    secondary=engine.registry.secondary
    assert isinstance(primary,LifecycleManagedCognitiveEngine)
    assert isinstance(secondary,LifecycleManagedCognitiveEngine)

    assert primary.configuration.model=="owner/primary-production:any"
    assert secondary.configuration.model=="owner/secondary-production:any"
    assert lifecycle.selection.primary.model=="owner/primary-production:any"
    assert lifecycle.selection.secondary is not None
    assert lifecycle.selection.secondary.model=="owner/secondary-production:any"
    assert configuration.provider.model=="qwen3.5:9b"


def test_fresh_production_configuration_is_dual_model_and_auto_managed(tmp_path):
    configuration=create_production_configuration(
        state_path=tmp_path/"fresh-production"/"sofia.db",
    )

    assert configuration.routing is not None
    assert configuration.routing.enabled is True
    assert configuration.routing.primary is not None
    assert configuration.routing.secondary is not None
    assert configuration.provider.model==configuration.routing.primary.model
    assert configuration.model_lifecycle.enabled is True
    assert configuration.model_lifecycle.auto_install_missing is True
