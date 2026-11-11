"""AG-D028 D028-01: read-only offline Core-free seed inspection.

The canonical PlatformReleaseVerifier authenticates publisher manifest and every
required byte. This extra packaging policy rejects personal Core, modules,
Ollama/model runtime and unreviewed distribution wheels in the Platform-only
seed. It NEVER installs/executes, initializes identity, downloads, signs or
creates new SAFE authority. The first clean-host native bootstrap remains a
separate signed OS executor deliverable and is NOT implemented by this module.
"""
from __future__ import annotations

from email.parser import BytesParser
from pathlib import Path
import re
import stat
import unicodedata
import zipfile

from sofia.platform.ops.platform_installer_bundle import (
    SignedInstallerRelease, verify_offline_installer_bundle, _bounded_file,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.artifact import validate_artifact_path
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget

_FORBIDDEN_DEPENDENCIES = frozenset((
    "sofia-core", "sofia-modules", "ollama", "sofia-ada-lyra",
))
_PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _inspect_dependency_wheel(path: Path, expected_sha: str, expected_size: int) -> str:
    """Inspect already signed exact wheel bytes for forbidden baseline packages."""
    if expected_size > 64 * 1024**2 or not _HEX.fullmatch(expected_sha):
        raise PlatformReleaseRejected("offline dependency exceeds reviewed seed bound")
    assert_no_redirected_components(path, include_leaf=True)
    actual_sha, _ = read_artifact_file(path, expected_size, include_data=False)
    if actual_sha != expected_sha:
        raise PlatformReleaseRejected("offline dependency bytes drifted after verification")
    try:
        # The canonical digest reader and zipfile both stream from the
        # approved path. Never materialize a 64MiB dependency wheel in RAM.
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 8192:
                raise PlatformReleaseRejected("dependency wheel exceeds inventory bound")
            metadata = [item for item in entries
                        if item.filename.endswith(".dist-info/METADATA")]
            if len(metadata) != 1 or metadata[0].file_size > 262144:
                raise PlatformReleaseRejected("offline dependency metadata missing or oversized")
            # Dependency metadata is signed via the existing manifest but
            # must also meet archive extraction/path policy BEFORE native
            # installation. A trusted signer does not make path traversal safe.
            if sum(item.file_size for item in entries) > 256 * 1024**2:
                raise PlatformReleaseRejected("offline dependency expansion exceeds bound")
            names = set()
            for item in entries:
                name = item.filename.rstrip("/")
                if item.orig_filename != item.filename:
                    raise PlatformReleaseRejected("ambiguous dependency ZIP entry")
                validate_artifact_path(name)
                normalized = unicodedata.normalize("NFKC", name).casefold()
                if normalized in names or stat.S_ISLNK(item.external_attr >> 16):
                    raise PlatformReleaseRejected("duplicate or redirected dependency entry")
                names.add(normalized)
                if (normalized.startswith(("sofia/core/", "sofia/modules/", "ollama/"))
                        or any(piece in normalized for piece in
                               ("/sofia/core/", "/sofia/modules/", "/ollama/"))):
                    raise PlatformReleaseRejected("offline dependency contains optional Core/model code")
            parsed = BytesParser().parsebytes(archive.read(metadata[0]))
            names = parsed.get_all("Name", [])
            if len(names) != 1 or not _PACKAGE_NAME.fullmatch(names[0]):
                raise PlatformReleaseRejected("offline dependency package name ambiguous")
            normalized = re.sub("[-_.]+", "-", names[0]).lower()
            if normalized in _FORBIDDEN_DEPENDENCIES:
                raise PlatformReleaseRejected("personal Core/model package in neutral seed")
    except PlatformReleaseRejected:
        # PlatformReleaseRejected inherits PermissionError/OSError. Preserve
        # explicit policy denials (especially forbidden Core/model packages)
        # instead of accidentally relabeling them as malformed ZIP errors.
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, UnicodeError, OSError, ValueError) as exc:
        raise PlatformReleaseRejected("malformed offline dependency wheel") from exc
    # A file replaced between the signed SHA read and ZIP metadata review
    # cannot produce a trusted neutral seed. Rehash the whole wheel after.
    after_sha, _ = read_artifact_file(
        path, expected_size, include_data=False,
    )
    if after_sha != expected_sha:
        raise PlatformReleaseRejected("offline dependency changed during ZIP review")
    return normalized


def review_core_free_offline_seed(
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
    source_kind: str = "offline_media",
) -> dict[str, object]:
    """Require local signed complete neutral Platform seed, never remote fallback.

    No public library wire/catalog schema is introduced before D028-00 freeze.
    The host must still separately authenticate and approve any install effect.
    """
    if source_kind not in ("offline_media", "verified_local_cache"):
        raise PlatformReleaseRejected(
            "offline seed source must be explicitly local, never hub/peer/WAN fetch"
        )
    reviewed = verify_offline_installer_bundle(
        bundle_root,
        trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=require_local_host,
    )
    root = Path(bundle_root).absolute()
    payload = loads_strict_model_json(
        _bounded_file(root / "release-manifest.json", 131_072).decode("utf-8")
    )
    manifest = PlatformReleaseManifest.from_payload(payload)
    if manifest.digest != reviewed.manifest_sha256:
        raise PlatformReleaseRejected("signed offline seed manifest changed after verification")
    required = {
        "sdk", "platform", "service", "python-runtime",
        "dependency-lock", "sbom", "provenance",
    }
    actual = {asset.kind for asset in manifest.assets}
    if not required.issubset(actual) or actual - (required | {"dependency"}):
        raise PlatformReleaseRejected("offline seed contains unexpected asset class")
    dependencies = []
    for asset in manifest.assets:
        if asset.kind == "dependency":
            dependency_path = root / "assets" / asset.reference.path
            dependencies.append(_inspect_dependency_wheel(
                dependency_path, asset.reference.sha256, asset.reference.size_bytes,
            ))
    if len(dependencies) != len(set(dependencies)):
        raise PlatformReleaseRejected("duplicate offline dependency distribution")
    return {
        "review_kind": "CORE_FREE_OFFLINE_SEED_ONLY",
        "source_kind": source_kind,
        "release_id": reviewed.release_id,
        "source_sha": reviewed.source_sha,
        "manifest_sha256": reviewed.manifest_sha256,
        "target": reviewed.target,
        "signer_key_id": reviewed.signer_key_id,
        "publisher_key_sha256": reviewed.trust_key_sha256,
        "neutral_components": ("sofia-sdk", "sofia-platform"),
        "dependency_distributions": tuple(sorted(dependencies)),
        "optional_core_count": 0,
        "optional_module_count": 0,
        "model_count": 0,
        "network_requested": False,
        "installation_performed": False,
        "service_registered": False,
        "owner_approved": False,
        "core_activated": False,
    }
