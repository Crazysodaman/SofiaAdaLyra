from dataclasses import replace

from sofia.config.model import FleetCognitionConfiguration
from sofia.cognition.model_lifecycle import (
    LifecycleManagedCognitiveEngine,
)
from sofia.cognition.routing import RoutingCognitiveEngine
from sofia.composition.engines import (
    create_cognitive_engine,
    create_model_lifecycle,
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
    lifecycle=create_model_lifecycle(configuration)
    engine=create_cognitive_engine(
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
    assert configuration.model_lifecycle.auto_install_missing is False


def test_legacy_auto_install_configuration_never_enables_host_model_download(
    tmp_path, monkeypatch,
):
    state_path=tmp_path/"protected"/"sofia.db"
    RuntimeUserSettingsStore(state_path).save(
        RuntimeUserSettings(
            cognitive_model_auto_manage=True,
            cognitive_model_auto_install=True,
        )
    )
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_INSTALL", "1")
    configured=create_production_configuration(state_path=state_path)
    assert configured.model_lifecycle.enabled is True
    assert configured.model_lifecycle.auto_install_missing is False


def test_gpu_less_canonical_host_does_not_manage_local_ollama_for_remote_only_fleet(tmp_path):
    """Artemis can own memory and runtime while Venus alone owns GPU inference."""
    configuration = create_production_configuration(
        state_path=tmp_path / "future-canonical" / "sofia.db",
    )
    remote_only = replace(
        configuration,
        fleet_cognition=FleetCognitionConfiguration(
            enabled=True,
            local_fallback=False,
            gpu_required=True,
            auto_provision_models=False,
            allowed_host_ids=("enrolled-venus-host-id",),
        ),
    )
    assert create_model_lifecycle(
        remote_only, local_host_id="enrolled-artemis-host-id",
    ) is None
    # The same operator-approved GPU host can still manage local model
    # residency when that host actually owns the canonical runtime.
    assert create_model_lifecycle(
        remote_only, local_host_id="enrolled-venus-host-id",
    ) is not None


def test_remote_only_host_stays_model_lifecycle_free_if_no_gpu_present(tmp_path):
    configuration = create_production_configuration(
        state_path=tmp_path / "future-host" / "sofia.db",
    )
    remote_only = replace(
        configuration,
        fleet_cognition=FleetCognitionConfiguration(
            enabled=True,
            allowed_host_ids=("verified-gpu-node",),
            local_fallback=False,
            gpu_required=True,
        ),
    )
    # This is a policy/host-ID preflight. No Ollama process, installation,
    # grant, migration or remote connection is made.
    assert create_model_lifecycle(remote_only, local_host_id="artemis") is None
