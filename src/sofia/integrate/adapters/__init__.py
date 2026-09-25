"""Concrete typed service adapters."""
from .home_assistant import HomeAssistantAdapter
from .portainer import PortainerAdapter
from .github import GitHubRepositoryAdapter
from .jmri import JmriAdapter
from .hyperv import HyperVAdapter

__all__ = [
    "HomeAssistantAdapter",
    "PortainerAdapter",
    "GitHubRepositoryAdapter",
    "JmriAdapter",
    "HyperVAdapter",
]
