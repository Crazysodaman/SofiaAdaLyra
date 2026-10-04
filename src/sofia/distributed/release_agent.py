"""Host-side signed release operations for the pinned-mTLS Fleet agent.

The controller never transfers executable bytes through the remote operation API.
A release must already exist in the host's configured inbox and must verify
against the host's trusted Ed25519 release key before staging or activation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from sofia.config.model import CURRENT_CONFIGURATION_SCHEMA_VERSION
from sofia.dev.release import ReleaseManifest
from sofia.dev.release_store import ReleaseStateStore
from sofia.dev.supply_chain import verify_release_evidence
from sofia.distributed.version import CURRENT_FLEET_PROTOCOL_VERSION
from sofia.run.release import ReleaseManager
from sofia.safe.audit import AuditChain
from sofia.safe.release import ReleaseActivationGuard, ReleaseVerificationError
from sofia.safe.release_ed25519 import Ed25519ReleaseSignatureVerifier
from sofia.state.sqlite_plane import SQLiteStatePlane


class AgentReleaseError(RuntimeError):
    pass


class AgentReleaseService:
    SIGNATURE_NAME = "release-signature.bin"
    SIGNER_ID_NAME = "signer-key-id.txt"

    def __init__(
        self,
        *,
        state_path: Path,
        release_root: Path,
        inbox_root: Path,
        trusted_key_file: Path,
        trusted_key_id: str,
    ) -> None:
        for value, label in (
            (state_path, "state_path"),
            (release_root, "release_root"),
            (inbox_root, "inbox_root"),
            (trusted_key_file, "trusted_key_file"),
        ):
            if not isinstance(value, Path):
                raise TypeError(f"{label} must be Path")
        if not state_path.is_file():
            raise FileNotFoundError("agent release state database does not exist")
        if not trusted_key_file.is_file():
            raise FileNotFoundError("trusted release public key does not exist")
        if not isinstance(trusted_key_id, str) or not trusted_key_id.strip():
            raise ValueError("trusted_key_id must be nonempty")

        self.state_path = state_path.resolve()
        self.release_root = release_root.resolve()
        self.inbox_root = inbox_root.resolve()
        self.trusted_key_id = trusted_key_id.strip()
        self.verifier = Ed25519ReleaseSignatureVerifier(
            {self.trusted_key_id: trusted_key_file}
        )
        plane = SQLiteStatePlane(self.state_path)
        self.store = ReleaseStateStore(plane)
        self.manager = ReleaseManager(
            release_root=self.release_root,
            store=self.store,
            guard=ReleaseActivationGuard(self.verifier),
            audit=AuditChain(self.state_path),
            state_schema_revision=plane.schema_revision,
            fleet_protocol_version=CURRENT_FLEET_PROTOCOL_VERSION,
            configuration_schema_version=CURRENT_CONFIGURATION_SCHEMA_VERSION,
        )

    def _bundle_path(self, release_id: str) -> Path:
        if not isinstance(release_id, str) or not release_id.strip():
            raise ValueError("release_id must be nonempty")
        candidate = (self.inbox_root / release_id).resolve()
        if candidate.parent != self.inbox_root:
            raise AgentReleaseError("release bundle path escaped configured inbox")
        if not candidate.is_dir():
            raise FileNotFoundError(
                f"signed release bundle is not present in host inbox: {release_id}"
            )
        return candidate

    def _signed_bundle(
        self,
        release_id: str,
        manifest_sha256: str,
    ) -> tuple[Path, ReleaseManifest, bytes, str]:
        bundle = self._bundle_path(release_id)
        manifest = verify_release_evidence(bundle)
        if manifest.release_id != release_id:
            raise AgentReleaseError("release bundle ID does not match request")
        if manifest.manifest_sha256 != manifest_sha256:
            raise AgentReleaseError("release manifest digest does not match request")

        signer_path = bundle / self.SIGNER_ID_NAME
        signature_path = bundle / self.SIGNATURE_NAME
        if not signer_path.is_file() or not signature_path.is_file():
            raise AgentReleaseError("release bundle is not signed")
        signer_key_id = signer_path.read_text(encoding="utf-8").strip()
        if signer_key_id != self.trusted_key_id:
            raise AgentReleaseError("release signer is not this host's trusted signer")
        signature = signature_path.read_bytes()
        if not signature:
            raise AgentReleaseError("release signature is empty")
        if not self.verifier.verify(
            manifest=manifest,
            signature=signature,
            signer_key_id=signer_key_id,
        ):
            raise ReleaseVerificationError("host rejected release signature")
        return bundle, manifest, signature, signer_key_id

    def current(self, _parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        active = self.store.active()
        if active is None:
            return {"active": False}
        return {
            "active": True,
            "release_id": active.get("release_id"),
            "manifest_sha256": active.get("manifest_sha256"),
            "previous_release_id": active.get("previous_release_id"),
            "verified_at": active.get("verified_at"),
        }

    def stage(self, parameters: dict[str, Any]) -> dict[str, Any]:
        release_id = str(parameters["release_id"])
        digest = str(parameters["manifest_sha256"]).casefold()
        bundle, manifest, _, _ = self._signed_bundle(release_id, digest)
        target = self.manager.stage(manifest, bundle / "artifact")
        return {
            "release_id": manifest.release_id,
            "manifest_sha256": manifest.manifest_sha256,
            "staged": True,
            "path": str(target),
        }

    def activate(self, parameters: dict[str, Any]) -> dict[str, Any]:
        release_id = str(parameters["release_id"])
        digest = str(parameters["manifest_sha256"]).casefold()
        bundle, manifest, signature, signer_key_id = self._signed_bundle(
            release_id,
            digest,
        )
        self.manager.activate(
            manifest=manifest,
            source_dir=bundle / "artifact",
            signature=signature,
            signer_key_id=signer_key_id,
            now=datetime.now(timezone.utc),
        )
        current = self.current()
        if (
            current.get("release_id") != release_id
            or current.get("manifest_sha256") != digest
        ):
            raise AgentReleaseError("active release did not converge after activation")
        return current

    def rollback(self, parameters: dict[str, Any]) -> dict[str, Any]:
        failed_release_id = str(parameters["failed_release_id"])
        reason = str(parameters.get("reason") or "fleet rollout rollback")
        if len(reason) > 500:
            raise ValueError("rollback reason is too long")
        self.manager.rollback_failed_release(
            failed_release_id=failed_release_id,
            reason=reason,
            now=datetime.now(timezone.utc),
        )
        return self.current()


def create_agent_release_service_from_environment() -> AgentReleaseService | None:
    state_raw = os.environ.get("SOFIA_AGENT_RELEASE_STATE_PATH", "").strip()
    inbox_raw = os.environ.get("SOFIA_AGENT_RELEASE_INBOX", "").strip()
    key_raw = os.environ.get("SOFIA_AGENT_RELEASE_TRUSTED_KEY_FILE", "").strip()
    key_id = os.environ.get("SOFIA_AGENT_RELEASE_TRUSTED_KEY_ID", "").strip()
    root_raw = os.environ.get("SOFIA_AGENT_RELEASE_ROOT", "").strip()

    required = (state_raw, inbox_raw, key_raw, key_id)
    if not any(required) and not root_raw:
        return None
    if not all(required):
        raise RuntimeError(
            "agent release operations require state path, inbox, trusted key file, "
            "and trusted key ID together"
        )
    state_path = Path(state_raw)
    release_root = (
        Path(root_raw)
        if root_raw
        else state_path.parent / "release-runtime"
    )
    return AgentReleaseService(
        state_path=state_path,
        release_root=release_root,
        inbox_root=Path(inbox_raw),
        trusted_key_file=Path(key_raw),
        trusted_key_id=key_id,
    )
