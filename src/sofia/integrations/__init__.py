"""Concrete integrations for Sofía's homelab and development environment."""
from .github import GitHubAdapter
from .discord import DiscordOperatorAdapter
from .home_assistant import HomeAssistantAdapter
from .hyperv import HyperVAdapter
from .jmri import JmriAdapter
from .local_maintenance import LocalMaintenanceAdapter
from .portainer import PortainerAdapter
from .ollama import OllamaAdapter
from .nws import NwsAdapter
from .sqlite import SQLiteReadAdapter
from .storage import StorageAdapter
__all__=["DiscordOperatorAdapter","GitHubAdapter","HomeAssistantAdapter","HyperVAdapter","JmriAdapter","LocalMaintenanceAdapter","PortainerAdapter","OllamaAdapter","NwsAdapter","SQLiteReadAdapter","StorageAdapter"]
