"""Configured production client for authenticated Fleet cognitive inference."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import UUID

from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.config.model import ProviderConfiguration
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.https_transport import PinnedHttpsRemoteTransport
from sofia.distributed.inference_control import DurableRemoteInferenceControl


class ConfiguredRemoteInferenceClient:
    """Open bounded durable Fleet state for one inference call at a time."""

    def __init__(
        self,
        state_path: Path,
        *,
        ca_file: Path,
        client_certificate: Path,
        client_private_key: Path,
        max_inventory_age: timedelta = timedelta(minutes=5),
    ) -> None:
        self.state_path = Path(state_path)
        self.base = self.state_path.parent
        self.ca_file = Path(ca_file)
        self.client_certificate = Path(client_certificate)
        self.client_private_key = Path(client_private_key)
        if not isinstance(max_inventory_age, timedelta) or (
            max_inventory_age <= timedelta(0)
        ):
            raise ValueError("max_inventory_age must be positive")
        self.max_inventory_age = max_inventory_age

    def infer(
        self,
        node_id: UUID,
        provider: ProviderConfiguration,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        endpoint_lookup = DurableEndpointPolicy(
            self.base / "remote-endpoints.db"
        )
        transport = PinnedHttpsRemoteTransport(
            endpoint_lookup.get,
            ca_file=self.ca_file,
            client_certificate=self.client_certificate,
            client_private_key=self.client_private_key,
        )
        control = DurableRemoteInferenceControl(
            transport=transport,
            identity_path=self.base / "remote-identities.db",
            endpoint_path=self.base / "remote-endpoints.db",
            authorization_path=self.base / "remote-grants.db",
            ledger_path=self.base / "remote-inference-ledger.db",
            max_inventory_age=self.max_inventory_age,
        )
        try:
            return control.infer(
                node_id=node_id,
                provider=provider,
                request=request,
                now=datetime.now(timezone.utc),
            )
        finally:
            control.close()
            endpoint_lookup.close()


def create_configured_remote_inference_client(
    state_path: Path,
) -> ConfiguredRemoteInferenceClient | None:
    values = {
        "ca": os.environ.get("SOFIA_REMOTE_CA", "").strip(),
        "cert": os.environ.get("SOFIA_REMOTE_CLIENT_CERT", "").strip(),
        "key": os.environ.get("SOFIA_REMOTE_CLIENT_KEY", "").strip(),
    }
    if not any(values.values()):
        return None
    if not all(values.values()):
        raise ValueError(
            "SOFIA_REMOTE_CA, SOFIA_REMOTE_CLIENT_CERT and "
            "SOFIA_REMOTE_CLIENT_KEY must be configured together"
        )
    raw_age = os.environ.get(
        "SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS",
        "300",
    )
    try:
        age = int(raw_age)
    except ValueError as exc:
        raise ValueError(
            "SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS must be an integer"
        ) from exc
    if age <= 0:
        raise ValueError(
            "SOFIA_REMOTE_MAX_INVENTORY_AGE_SECONDS must be positive"
        )
    return ConfiguredRemoteInferenceClient(
        Path(state_path),
        ca_file=Path(values["ca"]),
        client_certificate=Path(values["cert"]),
        client_private_key=Path(values["key"]),
        max_inventory_age=timedelta(seconds=age),
    )
