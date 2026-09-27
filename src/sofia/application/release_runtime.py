from __future__ import annotations

import os
from pathlib import Path

from sofia.config.model import CURRENT_CONFIGURATION_SCHEMA_VERSION, SofiaConfiguration
from sofia.dev.release_store import ReleaseStateStore
from sofia.distributed.version import CURRENT_FLEET_PROTOCOL_VERSION
from sofia.run.release import ReleaseManager
from sofia.safe.audit import AuditChain
from sofia.safe.release import ReleaseActivationGuard
from sofia.safe.release_ed25519 import Ed25519ReleaseSignatureVerifier
from sofia.state.plane import StatePlane


def create_release_manager(
    *,
    configuration: SofiaConfiguration,
    state_plane: StatePlane,
) -> ReleaseManager | None:
    """
    Compose the protected release manager only when a trusted key is explicit.

    Missing trust configuration disables self-release activation. There is no
    unsigned or development fallback.
    """
    key_file = os.environ.get(
        "SOFIA_RELEASE_TRUSTED_KEY_FILE",
        "",
    ).strip()
    key_id = os.environ.get(
        "SOFIA_RELEASE_TRUSTED_KEY_ID",
        "",
    ).strip()

    if not key_file and not key_id:
        return None
    if not key_file or not key_id:
        raise RuntimeError(
            "both SOFIA_RELEASE_TRUSTED_KEY_FILE and "
            "SOFIA_RELEASE_TRUSTED_KEY_ID are required"
        )

    release_root_value = os.environ.get(
        "SOFIA_RELEASE_ROOT",
        "",
    ).strip()
    release_root = (
        Path(release_root_value)
        if release_root_value
        else Path(configuration.state_path).parent / "release-runtime"
    )
    verifier = Ed25519ReleaseSignatureVerifier(
        {key_id: Path(key_file)}
    )
    return ReleaseManager(
        release_root=release_root,
        store=ReleaseStateStore(state_plane),
        guard=ReleaseActivationGuard(verifier),
        audit=AuditChain(configuration.state_path),
        state_schema_revision=state_plane.schema_revision,
        fleet_protocol_version=CURRENT_FLEET_PROTOCOL_VERSION,
        configuration_schema_version=CURRENT_CONFIGURATION_SCHEMA_VERSION,
    )
