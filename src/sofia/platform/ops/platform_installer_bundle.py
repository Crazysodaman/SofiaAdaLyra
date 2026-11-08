"""AG-D011 signed offline release *verification*.

This module consumes the existing canonical PlatformReleaseVerifier, never
signs/re-signs releases, selects them or changes an OS service. A public key
located inside the bundle is explicitly untrusted. The caller must supply an
independently provisioned trusted key and its independently pinned fingerprint,
exact source SHA, target, revision floor and predecessor.

No owner approval, service registration, Core or Fleet authority is implied.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import platform
import re

from sofia.platform.ops.platform_release import (
    PlatformReleaseRejected, PlatformReleaseVerifier,
)
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseTarget

_HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX_40 = re.compile(r"[0-9a-f]{40}\Z")


@dataclass(frozen=True, slots=True)
class SignedInstallerRelease:
    release_id: str
    revision: int
    manifest_sha256: str
    source_sha: str
    target: str
    signer_key_id: str
    trust_key_sha256: str
    asset_count: int

    def review(self) -> dict[str, object]:
        return {
            "schema": "aegis.installer.signed-review.v1",
            "result": "VERIFIED_RELEASE_BYTES_ONLY",
            "release_id": self.release_id,
            "revision": self.revision,
            "manifest_sha256": self.manifest_sha256,
            "source_sha": self.source_sha,
            "target": self.target,
            "signer_key_id": self.signer_key_id,
            "trust_key_sha256": self.trust_key_sha256,
            "asset_count": self.asset_count,
            "owner_approved": False,
            "executed": False,
            "os_service_registered": False,
            "core_activated": False,
            "fleet_enrolled": False,
        }


def host_release_target() -> PlatformReleaseTarget:
    """Report only exact supported host types; refuse unsupported hosts."""
    machine = platform.machine().lower()
    if machine not in ("amd64", "x86_64"):
        raise PlatformReleaseRejected("unsupported architecture for Aegis Platform 1.0")
    if os.name == "nt":
        return PlatformReleaseTarget.WINDOWS_X86_64
    if os.name != "posix" or platform.system() != "Linux":
        raise PlatformReleaseRejected("unsupported host operating system")
    fields = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key in ("ID", "VERSION_ID"):
                fields[key] = value.strip().strip('"')
    except (OSError, UnicodeError) as error:
        raise PlatformReleaseRejected("cannot establish trusted Debian target") from error
    if fields != {"ID": "debian", "VERSION_ID": "12"}:
        raise PlatformReleaseRejected("installer requires exactly Debian 12")
    return PlatformReleaseTarget.DEBIAN12_X86_64


def _bounded_file(path: Path, limit: int) -> bytes:
    assert_no_redirected_components(path, include_leaf=True)
    info = path.stat(follow_symlinks=False)
    if not 1 <= info.st_size <= limit:
        raise PlatformReleaseRejected("installer metadata outside bounded size")
    return read_artifact_file(path, info.st_size, include_data=True)[1]


def verify_offline_installer_bundle(
    bundle_root: Path | str,
    *,
    trusted_public_key: Path | str,
    trusted_key_sha256: str,
    trusted_signer_key_id: str,
    expected_source_sha: str,
    expected_target: PlatformReleaseTarget,
    minimum_revision: int,
    expected_parent_manifest_sha256: str | None = None,
    require_local_host: bool = True,
) -> SignedInstallerRelease:
    """Verify signed release and complete required assets without mutating state.

    Trust must be pinned *outside* the signed bundle. This is a preflight,
    not a permission or the native installer. Every release byte is checked by
    the production Platform verifier, not by a parallel signature algorithm.
    """
    if not isinstance(expected_target, PlatformReleaseTarget):
        raise TypeError("typed expected target required")
    if not isinstance(trusted_key_sha256, str) or not _HEX_64.fullmatch(trusted_key_sha256):
        raise PlatformReleaseRejected("externally pinned trusted key fingerprint required")
    if not isinstance(expected_source_sha, str) or not _HEX_40.fullmatch(expected_source_sha):
        raise PlatformReleaseRejected("externally pinned exact source SHA required")
    if not isinstance(trusted_signer_key_id, str) or not 1 <= len(trusted_signer_key_id) <= 128:
        raise PlatformReleaseRejected("reviewed signer key identity required")
    if type(minimum_revision) is not int or minimum_revision < 1:
        raise PlatformReleaseRejected("positive durable revision floor required")
    if expected_parent_manifest_sha256 is not None and (
        not isinstance(expected_parent_manifest_sha256, str)
        or not _HEX_64.fullmatch(expected_parent_manifest_sha256)
    ):
        raise PlatformReleaseRejected("invalid expected predecessor digest")
    if require_local_host and expected_target != host_release_target():
        raise PlatformReleaseRejected("release target does not match observed host")

    root = Path(bundle_root).absolute()
    key = Path(trusted_public_key).absolute()
    assert_no_redirected_components(root, include_leaf=True)
    assert_no_redirected_components(key, include_leaf=True)
    if not root.is_dir() or key == root or root in key.parents:
        raise PlatformReleaseRejected("publisher trust must originate outside release bundle")
    key_bytes = _bounded_file(key, 16_384)
    digest = sha256(key_bytes).hexdigest()
    if digest != trusted_key_sha256:
        raise PlatformReleaseRejected("pinned publisher key fingerprint does not match")
    payload = loads_strict_model_json(
        _bounded_file(root / "release-manifest.json", 131_072).decode("utf-8")
    )
    envelope = loads_strict_model_json(
        _bounded_file(root / "release-signature.json", 16_384).decode("utf-8")
    )
    if type(envelope) is not dict or set(envelope) != {"signer_key_id", "signature_b64"}:
        raise PlatformReleaseRejected("release signature envelope is not canonical")
    if envelope["signer_key_id"] != trusted_signer_key_id:
        raise PlatformReleaseRejected("untrusted or unexpected release signer")
    verifier = PlatformReleaseVerifier({trusted_signer_key_id: key_bytes})
    manifest = verifier.verify(
        payload,
        signature_b64=envelope["signature_b64"],
        signer_key_id=trusted_signer_key_id,
        assets_root=root / "assets",
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
    )
    return SignedInstallerRelease(
        release_id=manifest.release_id,
        revision=manifest.revision,
        manifest_sha256=manifest.digest,
        source_sha=manifest.source_sha,
        target=manifest.target.value,
        signer_key_id=trusted_signer_key_id,
        trust_key_sha256=digest,
        asset_count=len(manifest.assets),
    )
