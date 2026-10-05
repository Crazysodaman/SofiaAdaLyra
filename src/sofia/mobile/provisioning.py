"""Runtime provisioning for the private Android companion endpoint."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from sofia.config import SofiaConfiguration
from sofia.safe.secret_store import ProtectedSecretStore

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
    token = os.environ.get("SOFIA_MOBILE_TOKEN", "").strip()
    if token:
        return 32 <= len(token) <= 512
    return ProtectedSecretStore.for_state_path(state_path).exists(
        "mobile-api-token"
    )


@dataclass(frozen=True, slots=True)
class MobileProvisioning:
    enabled: bool
    server: MobileServerConfiguration
    token: str | None

    @classmethod
    def from_runtime(cls, configuration: SofiaConfiguration) -> "MobileProvisioning":
        if not isinstance(configuration, SofiaConfiguration):
            raise TypeError("configuration must be SofiaConfiguration")
        enabled = _flag("SOFIA_MOBILE_ENABLED")
        token = os.environ.get("SOFIA_MOBILE_TOKEN", "").strip() or None
        if token is None:
            token = ProtectedSecretStore.for_state_path(
                configuration.state_path
            ).get("mobile-api-token")
        raw_certificate = os.environ.get("SOFIA_MOBILE_TLS_CERT", "").strip()
        raw_key = os.environ.get("SOFIA_MOBILE_TLS_KEY", "").strip()
        server = MobileServerConfiguration(
            host=os.environ.get("SOFIA_MOBILE_HOST", "127.0.0.1").strip(),
            port=int(os.environ.get("SOFIA_MOBILE_PORT", "8766")),
            certificate=Path(raw_certificate) if raw_certificate else None,
            private_key=Path(raw_key) if raw_key else None,
        )
        if enabled and token is None:
            raise ValueError(
                "enabled mobile companion requires SOFIA_MOBILE_TOKEN or "
                "the protected mobile-api-token secret"
            )
        return cls(enabled=enabled, server=server, token=token)

    def require_token(self) -> str:
        if not self.enabled or self.token is None:
            raise RuntimeError("mobile companion is not provisioned")
        return self.token
