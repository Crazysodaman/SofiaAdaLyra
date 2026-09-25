"""Concrete integrations for Sofía's homelab and development environment."""
from .github import GitHubAdapter
from .home_assistant import HomeAssistantAdapter
from .hyperv import HyperVAdapter
from .jmri import JmriAdapter
from .portainer import PortainerAdapter
from .ollama import OllamaAdapter
from .sqlite import SQLiteReadAdapter
from .storage import StorageAdapter
__all__=["GitHubAdapter","HomeAssistantAdapter","HyperVAdapter","JmriAdapter","PortainerAdapter","OllamaAdapter","SQLiteReadAdapter","StorageAdapter"]
