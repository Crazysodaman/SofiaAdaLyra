"""Platform configuration exports loaded lazily for role-only clients."""
from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    **{name: ("authority", name) for name in (
        "ConfigurationPrecedence", "ConfigurationResolver", "ConfigurationValue",
    )},
    **{name: ("defaults", name) for name in (
        "create_default_configuration", "create_production_configuration",
        "production_state_path", "production_storage_layout",
    )},
    **{name: ("model_catalog", name) for name in (
        "DEFAULT_PROVIDER_MODEL", "LOCAL_MODEL_PRESETS",
        "RECOMMENDED_PRIMARY_MODEL", "RECOMMENDED_SECONDARY_MODEL",
        "known_local_model_names",
    )},
    **{name: ("model", name) for name in (
        "CoreWorkerConfiguration", "CognitiveRoutingConfiguration",
        "FleetBootstrapConfiguration", "FleetCognitionConfiguration",
        "FleetDiscoveryConfiguration", "ModelLifecycleConfiguration",
        "ProviderConfiguration", "SofiaConfiguration",
    )},
    **{name: ("roles", name) for name in (
        "PlatformRole", "PlatformRoleConfiguration",
    )},
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute)
    globals()[name] = value
    return value
