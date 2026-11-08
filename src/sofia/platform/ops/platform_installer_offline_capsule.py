"""AG-D011/D028-01 reproducible Core-free offline *media* assembly.

This runs on the RELEASE BUILD HOST, not the clean installation target.
It reuses the canonical signed release verifier and packages the prebuilt
Windows/Debian Python runtime, service executable and wheels already present
in the signed release. No independent signing system, owner auth, installer,
Core identity or native activation is introduced.

IMPORTANT: A capsule digest alone does not authenticate its publisher.
The launcher scripts/theme are not inside the existing signed PlatformRelease
manifest and MUST receive independent publisher-signed delivery attestation
before the final self-contained installer is considered trusted.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile
import zipfile

from sofia.platform.ops.platform_installer_offline_seed import review_core_free_offline_seed
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import (
    assert_no_redirected_components, ensure_owner_private_directory,
)
from sofia.sdk.cognition_json import loads_strict_model_json
from sofia.sdk.platform_release import PlatformReleaseManifest, PlatformReleaseTarget

_MAX_MEDIA_BYTES = 1024**3 + 2 * 1024**2
_STATIC = (
    ("packaging/installers/install-aegis.sh", "aegis/install-aegis.sh"),
    ("packaging/installers/Install-Aegis.ps1", "aegis/Install-Aegis.ps1"),
    ("contracts/ui/aegis-theme-v1.json", "aegis/contracts/ui/aegis-theme-v1.json"),
)
_STAMP = (1980, 1, 1, 0, 0, 0)


def _read_expected(path: Path, *, maximum: int, exact: int | None = None) -> bytes:
    assert_no_redirected_components(path, include_leaf=True)
    stat_result = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(stat_result.st_mode)
            or not 1 <= stat_result.st_size <= maximum
            or (exact is not None and stat_result.st_size != exact)):
        raise PlatformReleaseRejected("offline capsule member has unsafe file bounds")
    return read_artifact_file(path, stat_result.st_size, include_data=True)[1]


def _archive_member(zipper: zipfile.ZipFile, name: str, data: bytes) -> None:
    if not name.startswith("aegis/") or any(piece in (".", "..", "") for piece in name.split("/")):
        raise PlatformReleaseRejected("offline capsule member name invalid")
    info = zipfile.ZipInfo(filename=name, date_time=_STAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    zipper.writestr(info, data)


def build_reviewed_offline_capsule(
    *,
    staged_release: Path | str,
    project_root: Path | str,
    output_path: Path | str,
    trusted_public_key: Path | str,
    trusted_key_sha256: str,
    trusted_signer_key_id: str,
    expected_source_sha: str,
    expected_target: PlatformReleaseTarget,
    minimum_revision: int,
    expected_parent_manifest_sha256: str | None = None,
) -> dict[str, object]:
    """Produce deterministic media containing reviewed signed bytes only.

    A release builder/operator must separately authenticate this capsule's
    launchers and media digest and provide current SAFE execution authority.
    This helper CANNOT execute or approve an installation.
    """
    root = Path(staged_release).absolute()
    project = Path(project_root).absolute()
    destination = Path(output_path).absolute()
    for value in (root, project, destination):
        assert_no_redirected_components(value, include_leaf=True)
    if destination == root or root in destination.parents:
        raise PlatformReleaseRejected("do not place capsule output inside signed release")
    if destination.exists() or destination.is_symlink():
        raise PlatformReleaseRejected("offline release output already exists")
    if not project.is_dir() or not root.is_dir():
        raise PlatformReleaseRejected("reviewed source and signed staging required")
    result = review_core_free_offline_seed(
        root, trusted_public_key=trusted_public_key,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=False,
        source_kind="offline_media",
    )
    manifest_bytes = _read_expected(root / "release-manifest.json", maximum=131072)
    manifest = PlatformReleaseManifest.from_payload(
        loads_strict_model_json(manifest_bytes.decode("utf-8"))
    )
    if manifest.digest != result["manifest_sha256"]:
        raise PlatformReleaseRejected("signed manifest drifted during capsule assembly")
    signature_bytes = _read_expected(root / "release-signature.json", maximum=8192)
    members = [
        ("aegis/release-manifest.json", manifest_bytes),
        ("aegis/release-signature.json", signature_bytes),
    ]
    for asset in manifest.assets:
        reference = asset.reference
        file = root / "assets" / reference.path
        value = _read_expected(file, maximum=512 * 1024**2, exact=reference.size_bytes)
        if sha256(value).hexdigest() != reference.sha256:
            raise PlatformReleaseRejected("signed asset drifted during capsule build")
        members.append(("aegis/assets/" + reference.path, value))
    for src, target in _STATIC:
        source = project.joinpath(*src.split("/"))
        members.append((target, _read_expected(source, maximum=2 * 1024**2)))
    members.sort(key=lambda x: x[0])
    if sum(len(data) for _, data in members) > _MAX_MEDIA_BYTES:
        raise PlatformReleaseRejected("offline capsule exceeds reviewed media bound")

    ensure_owner_private_directory(destination.parent)
    descriptor, tempname = tempfile.mkstemp(prefix=".aegis-offline-", suffix=".zip",
                                             dir=destination.parent)
    temporary = Path(tempname)
    try:
        os.close(descriptor)
        with zipfile.ZipFile(temporary, mode="w", allowZip64=True) as zipper:
            for name, data in members:
                _archive_member(zipper, name, data)
        with zipfile.ZipFile(temporary, mode="r") as zipper:
            filenames = zipper.namelist()
            if len(filenames) != len(members) or filenames != [n for n, _ in members]:
                raise PlatformReleaseRejected("archive inventory differs after assembly")
            for name, expected in members:
                if sha256(zipper.read(name)).digest() != sha256(expected).digest():
                    raise PlatformReleaseRejected("archive member bytes differ")
        size = temporary.stat(follow_symlinks=False).st_size
        if size < 1 or size > _MAX_MEDIA_BYTES:
            raise PlatformReleaseRejected("produced archive size outside bound")
        hasher = sha256()
        with temporary.open("rb") as source:
            while block := source.read(1024**2):
                hasher.update(block)
        digest = hasher.hexdigest()
        if destination.exists() or destination.is_symlink():
            raise PlatformReleaseRejected("output path changed during assembly")
        # Atomic fail-if-exists; no overwrite of previously reviewed media.
        os.link(temporary, destination)
        return {
            "schema": "aegis.installer.offline-capsule-build.v1",
            "result": "SIGNED_RELEASE_BYTES_PACKAGED_NOT_INSTALLED",
            "capsule_sha256": digest,
            "capsule_size_bytes": size,
            "release_manifest_sha256": manifest.digest,
            "release_id": manifest.release_id,
            "revision": manifest.revision,
            "target": manifest.target.value,
            "signer_key_id": trusted_signer_key_id,
            "publisher_public_key_sha256": trusted_key_sha256,
            "release_manifest_signature_verified": True,
            "release_assets_verified": True,
            "launcher_publisher_signature_verified": False,
            "self_contained_native_installer_certified": False,
            "owner_authorized": False,
            "installed": False,
            "core_activated": False,
            "media_artifact_count": len(members),
        }
    finally:
        temporary.unlink(missing_ok=True)
