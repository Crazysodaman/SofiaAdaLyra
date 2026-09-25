"""Select the local read-only system inspection backend."""
from __future__ import annotations

import sys

from sofia.system.backend import SystemCapabilityBackend
from sofia.system.linux import LinuxSystemCapabilityBackend
from sofia.system.windows import WindowsSystemCapabilityBackend


def create_system_backend() -> SystemCapabilityBackend | None:
    if sys.platform == "win32":
        return WindowsSystemCapabilityBackend()
    if sys.platform.startswith("linux"):
        return LinuxSystemCapabilityBackend()
    return None
