"""Runtime provisioning for the private Android companion endpoint."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3

from sofia.config import SofiaConfiguration
from .pairing import MobileDeviceCredentialStore

from .server import MobileServerConfiguration


def _flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().casefold()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    raise ValueError(f"{name} must be a boolean flag")


def mobile_companion_ready(state_path: Path | str) -> bool:
    """Report whether the authenticated endpoint has usable runtime credentials."""
    if not _flag("SOFIA_MOBILE_ENABLED"):
        return False
    # ACT should only claim mobile delivery is configured if at least
    # one individually authenticated, nonrevoked recipient exists.
    try:
        return MobileDeviceCredentialStore(state_path).active_count() > 0
    except (FileNotFoundError, OSError, sqlite3.Error):
        return False


@dataclass(frozen=True, slots=True)
class MobileProvisioning:
    enabled: bool
    server: MobileServerConfiguration
    enrolled_devices: int

    @classmethod
    def from_runtime(cls, configuration: SofiaConfiguration) -> "MobileProvisioning":
        if not isinstance(configuration, SofiaConfiguration):
            raise TypeError("configuration must be SofiaConfiguration")
        enabled = _flag("SOFIA_MOBILE_ENABLED")
        if enabled and os.environ.get("SOFIA_MOBILE_TOKEN", "").strip():
            raise ValueError(
                "SOFIA_MOBILE_TOKEN was retired; operator must enroll each phone "
                "using python -m sofia.mobile.pairing"
            )
        # The server may listen with zero enrolled devices so the operator
        # can securely pair later. Unenrolled requests always receive 401.
        count = MobileDeviceCredentialStore(
            configuration.state_path
        ).active_count() if enabled else 0
        raw_certificate = os.environ.get("SOFIA_MOBILE_TLS_CERT", "").strip()
        raw_key = os.environ.get("SOFIA_MOBILE_TLS_KEY", "").strip()
        server = MobileServerConfiguration(
            host=os.environ.get("SOFIA_MOBILE_HOST", "127.0.0.1").strip(),
            port=int(os.environ.get("SOFIA_MOBILE_PORT", "8766")),
            certificate=Path(raw_certificate) if raw_certificate else None,
            private_key=Path(raw_key) if raw_key else None,
        )
        return cls(enabled=enabled, server=server, enrolled_devices=count)
