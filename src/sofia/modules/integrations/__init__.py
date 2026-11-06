"""Concrete integrations, loaded independently on first explicit access."""
from importlib import import_module


_EXPORTS = {
    "GitHubAdapter": "github",
    "DiscordOperatorAdapter": "discord",
    "HomeAssistantAdapter": "home_assistant",
    "HyperVAdapter": "hyperv",
    "JmriAdapter": "jmri",
    "LocalMaintenanceAdapter": "local_maintenance",
    "PortainerAdapter": "portainer",
    "OllamaAdapter": "ollama",
    "NwsAdapter": "nws",
    "SQLiteReadAdapter": "sqlite",
    "StorageAdapter": "storage",
}
__all__ = [
    "DiscordOperatorAdapter", "GitHubAdapter", "HomeAssistantAdapter",
    "HyperVAdapter", "JmriAdapter", "LocalMaintenanceAdapter", "PortainerAdapter",
    "OllamaAdapter", "NwsAdapter", "SQLiteReadAdapter", "StorageAdapter",
]


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
