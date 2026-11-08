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
import re
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
    ("packaging/installers/debian12-offline-prerequisites.sh", "aegis/debian12-offline-prerequisites.sh"),
    ("packaging/installers/verify-aegis-capsule.sh", "aegis/verify-aegis-capsule.sh"),
    ("packaging/installers/inspect-aegis-capsule-members.sh", "aegis/inspect-aegis-capsule-members.sh"),
    ("packaging/installers/observe-debian12-service.sh", "aegis/observe-debian12-service.sh"),
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


def offline_capsule_publisher_seal_message(
    *, capsule_sha256: str, signer_key_id: str,
) -> bytes:
    """Exact message for the EXISTING publisher key to sign, never a new key.

    Same-byte contract as verify-aegis-capsule.sh. An approved release
    signing workflow signs these bytes only in the owner-authorized
    production release environment, never on this draft branch.
    """
    if (not isinstance(capsule_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", capsule_sha256) is None):
        raise ValueError("canonical lowercase capsule digest required")
    if (not isinstance(signer_key_id, str)
            or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", signer_key_id) is None):
        raise ValueError("bounded release publisher key ID required")
    return (
        b"aegis.offline.capsule.v1\0"
        + signer_key_id.encode("ascii")
        + b"\0"
        + capsule_sha256.encode("ascii")
    )


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
    exact_signed_assets = []
    for asset in manifest.assets:
        reference = asset.reference
        file = root / "assets" / reference.path
        value = _read_expected(file, maximum=512 * 1024**2, exact=reference.size_bytes)
        if sha256(value).hexdigest() != reference.sha256:
            raise PlatformReleaseRejected("signed asset drifted during capsule build")
        members.append(("aegis/assets/" + reference.path, value))
        exact_signed_assets.append({
            "kind": asset.kind,
            "path": reference.path,
            "sha256": reference.sha256,
            "size_bytes": reference.size_bytes,
        })
    independently_unsigned_delivery_assets = []
    for src, target in _STATIC:
        source = project.joinpath(*src.split("/"))
        data = _read_expected(source, maximum=2 * 1024**2)
        members.append((target, data))
        independently_unsigned_delivery_assets.append({
            "path": target,
            "sha256": sha256(data).hexdigest(),
            "size_bytes": len(data),
            "publisher_signature_verified": False,
        })
    # The independently signed OUTER capsule carries an OS-native digest
    # inventory for every file other than the index itself. The outer seal
    # authenticates these bytes, and the canonical PlatformReleaseVerifier
    # remains the independent inner SDK/service/runtime signature authority.
    # Bounded ASCII tab format avoids requiring Python or jq before verification.
    members.sort(key=lambda x: x[0])
    index_lines = ["aegis.delivery-index.v1"]
    for filename, data in members:
        if (not filename.isascii()
                or any(c in filename for c in ("\t", "\n", "\r"))):
            raise PlatformReleaseRejected("unsafe offline delivery inventory path")
        index_lines.append(f"{sha256(data).hexdigest()}\t{len(data)}\t{filename}")
    index_bytes = ("\n".join(index_lines) + "\n").encode("ascii")
    if len(index_bytes) > 131072 or len(index_lines) > 130:
        raise PlatformReleaseRejected("offline delivery index outside fixed bounds")
    index_name = "aegis/delivery-index.v1"
    members.append((index_name, index_bytes))
    independently_unsigned_delivery_assets.append({
        "path": index_name,
        "sha256": sha256(index_bytes).hexdigest(),
        "size_bytes": len(index_bytes),
        "publisher_signature_verified": False,
    })
    members.sort(key=lambda x: x[0])
    if len({name.casefold() for name, _ in members}) != len(members):
        raise PlatformReleaseRejected("offline capsule has ambiguous duplicate member paths")
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
            "publisher_capsule_seal_schema": "aegis.offline.capsule.v1",
            "publisher_capsule_seal_message_sha256": sha256(
                offline_capsule_publisher_seal_message(
                    capsule_sha256=digest, signer_key_id=trusted_signer_key_id,
                )
            ).hexdigest(),
            "publisher_capsule_seal_signature_verified": False,
            "release_manifest_sha256": manifest.digest,
            "release_id": manifest.release_id,
            "revision": manifest.revision,
            "target": manifest.target.value,
            "signer_key_id": trusted_signer_key_id,
            "publisher_public_key_sha256": trusted_key_sha256,
            "publisher_revocation_fresh": False,
            "source_sha": manifest.source_sha,
            "signed_parent_manifest_sha256": manifest.parent_manifest_sha256,
            "release_manifest_signature_verified": True,
            "release_assets_verified": True,
            "offline_delivery_index_sha256": sha256(index_bytes).hexdigest(),
            "offline_delivery_member_count": len(members),
            "verified_release_asset_count": len(exact_signed_assets),
            "signed_release_assets": tuple(exact_signed_assets),
            "unsigned_delivery_assets": tuple(independently_unsigned_delivery_assets),
            "launcher_publisher_signature_verified": False,
            "self_contained_native_installer_certified": False,
            "owner_authorized": False,
            "installed": False,
            "core_activated": False,
            "media_artifact_count": len(members),
        }
    finally:
        temporary.unlink(missing_ok=True)
