"""Read-only trust bridge: publisher-sealed offline ZIP -> staged inner B1 release.

The same independently pinned Ed25519 publisher key authenticates the complete
outer delivery ZIP and the existing PlatformReleaseManifest. No second signer,
installer executor, Core, Fleet enrollment, approval, or state database.
The staged directory must be a private product of the stock offline stager.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
import stat
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sofia.platform.ops.platform_installer_bundle import verify_offline_installer_bundle
from sofia.platform.ops.platform_installer_offline_capsule import (
    offline_capsule_publisher_seal_message,
)
from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.platform_release import PlatformReleaseTarget

_MAX_CAPSULE = 1024 ** 3 + 2 * 1024 ** 2
_MAX_MEMBER = 512 * 1024 ** 2
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ENTRY = re.compile(r"(aegis/[A-Za-z0-9._/+@-]{1,240})\Z")


def _private_file(path: Path, *, maximum: int, exact: int | None = None) -> bytes:
    """Read only small metadata, never an unbounded package blob."""
    assert_no_redirected_components(path, include_leaf=True)
    details = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
            or not 1 <= details.st_size <= maximum
            or (exact is not None and details.st_size != exact)):
        raise PlatformReleaseRejected("unsafe bounded offline metadata")
    return read_artifact_file(
        path, details.st_size, include_data=True,
    )[1]


def _sealed_capsule_digest(path: Path) -> str:
    """Stream the complete sealed ZIP, including media larger than 512 MiB."""
    assert_no_redirected_components(path, include_leaf=True)
    before = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_CAPSULE):
        raise PlatformReleaseRejected("sealed capsule size or inode invalid")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)
        original = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (not stat.S_ISREG(opened.st_mode) or
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != original):
            raise PlatformReleaseRejected("sealed capsule inode substituted")
        digest = sha256()
        received = 0
        with os.fdopen(fd, "rb", closefd=False) as reader:
            while chunk := reader.read(65536):
                received += len(chunk)
                if received > before.st_size:
                    raise PlatformReleaseRejected("sealed capsule expanded during verification")
                digest.update(chunk)
        after = os.fstat(fd)
        final = path.stat(follow_symlinks=False)
        if (received != before.st_size or
                original != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                or original != (final.st_dev, final.st_ino,
                               final.st_size, final.st_mtime_ns)):
            raise PlatformReleaseRejected("sealed capsule changed during inspection")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _validated_index(raw: bytes) -> dict[str, tuple[str, int]]:
    if not 24 <= len(raw) <= 131072 or not raw.endswith(b"\n"):
        raise PlatformReleaseRejected("offline delivery index length invalid")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise PlatformReleaseRejected("offline index must be ASCII") from exc
    if not lines or lines[0] != "aegis.delivery-index.v1":
        raise PlatformReleaseRejected("offline delivery index schema differs")
    if not 1 <= len(lines) - 1 <= 128:
        raise PlatformReleaseRejected("offline delivery index inventory invalid")
    entries: dict[str, tuple[str, int]] = {}
    previous = ""
    total = 0
    for line in lines[1:]:
        fields = line.split("\t")
        if len(fields) != 3:
            raise PlatformReleaseRejected("offline delivery member record malformed")
        digest, length, name = fields
        pieces = name.split("/")
        if (not _HEX64.fullmatch(digest) or
                not re.fullmatch(r"[1-9][0-9]{0,11}", length) or
                _ENTRY.fullmatch(name) is None or
                any(piece in ("", ".", "..") for piece in pieces) or
                name == "aegis/delivery-index.v1" or
                name <= previous):
            raise PlatformReleaseRejected("offline delivery index path invalid")
        size = int(length)
        total += size
        if size > _MAX_MEMBER or total > _MAX_CAPSULE:
            raise PlatformReleaseRejected("offline delivery member exceeds bound")
        entries[name] = (digest, size)
        previous = name
    if len({name.casefold() for name in entries}) != len(entries):
        raise PlatformReleaseRejected("ambiguous offline delivery member names")
    return entries


def review_staged_publisher_signed_capsule(
    *, capsule: Path | str, capsule_signature: Path | str,
    staged_directory: Path | str,
    trusted_public_key: Path | str, trusted_key_sha256: str,
    trusted_signer_key_id: str, expected_source_sha: str,
    expected_target: PlatformReleaseTarget, minimum_revision: int,
    expected_parent_manifest_sha256: str | None = None,
    require_local_host: bool = True,
) -> dict[str, object]:
    """Reverify sealed ZIP, staged members and canonical signed inner B1.

    This function is read-only. The key PIN must be independently obtained and
    publisher revocation separately verified. It does NOT authorize an install.
    """
    if os.name != "posix" or expected_target is not PlatformReleaseTarget.DEBIAN12_X86_64:
        raise PlatformReleaseRejected("reviewed offline capsule staging is Debian-only")
    if type(trusted_key_sha256) is not str or _HEX64.fullmatch(trusted_key_sha256) is None:
        raise PlatformReleaseRejected("independent publisher SHA-256 pin required")
    stage = Path(staged_directory).absolute()
    root = stage / "aegis"
    capsule_path = Path(capsule).absolute()
    key_path = Path(trusted_public_key).absolute()
    signature_path = Path(capsule_signature).absolute()
    for path in (stage, capsule_path, key_path, signature_path):
        assert_no_redirected_components(path, include_leaf=True)
    if (not stage.is_dir() or not root.is_dir()
            or any(path == stage or stage in path.parents
                   for path in (capsule_path, key_path, signature_path))):
        raise PlatformReleaseRejected("reviewed stage and independent trust locations required")
    # The stock stage command leaves only private regular files and 0700 dirs.
    for path in (stage, root):
        info = path.stat(follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise PlatformReleaseRejected("offline stage directory is not owner-private")

    public = _private_file(key_path, maximum=16384)
    if sha256(public).hexdigest() != trusted_key_sha256:
        raise PlatformReleaseRejected("external publisher pin differs")
    try:
        signer = serialization.load_pem_public_key(public)
        if not isinstance(signer, Ed25519PublicKey):
            raise PlatformReleaseRejected("publisher signing algorithm not Ed25519")
        signature = _private_file(signature_path, maximum=64, exact=64)
        capsule_digest = _sealed_capsule_digest(capsule_path)
        signer.verify(
            signature,
            offline_capsule_publisher_seal_message(
                capsule_sha256=capsule_digest, signer_key_id=trusted_signer_key_id,
            ),
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise PlatformReleaseRejected("outer publisher capsule seal rejected") from exc

    try:
        with zipfile.ZipFile(capsule_path, "r") as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= 130:
                raise PlatformReleaseRejected("offline capsule member count invalid")
            names = [entry.filename for entry in infos]
            if (len(set(names)) != len(names)
                    or len({name.casefold() for name in names}) != len(names)
                    or any(entry.is_dir() or entry.compress_type != zipfile.ZIP_STORED
                           or not stat.S_ISREG(entry.external_attr >> 16)
                           for entry in infos)):
                raise PlatformReleaseRejected("offline capsule layout rejected")
            inventory = archive.getinfo("aegis/delivery-index.v1")
            if not 1 <= inventory.file_size <= 131072:
                raise PlatformReleaseRejected("offline inventory unbounded")
            signed_index = archive.read(inventory)
            expected = _validated_index(signed_index)
            expected_names = set(expected) | {"aegis/delivery-index.v1"}
            if set(names) != expected_names:
                raise PlatformReleaseRejected("offline capsule member list differs")

        # Require exact staged file closure, no foreign files or symlinks.
        observed_files = set()
        for path in stage.rglob("*"):
            assert_no_redirected_components(path, include_leaf=True)
            info = path.stat(follow_symlinks=False)
            if path.is_dir():
                if (not stat.S_ISDIR(info.st_mode) or
                        info.st_uid != os.geteuid() or
                        stat.S_IMODE(info.st_mode) != 0o700):
                    raise PlatformReleaseRejected("offline stage directory changed")
                continue
            if (not stat.S_ISREG(info.st_mode) or
                    info.st_nlink != 1 or
                    info.st_uid != os.geteuid() or
                    stat.S_IMODE(info.st_mode) != 0o600):
                raise PlatformReleaseRejected("offline staged file origin changed")
            observed_files.add(path.relative_to(stage).as_posix())
        if observed_files != expected_names:
            raise PlatformReleaseRejected("offline staged file closure differs")
        if _private_file(
            stage / "aegis/delivery-index.v1", maximum=131072,
        ) != signed_index:
            raise PlatformReleaseRejected("staged delivery index differs from sealed ZIP")
        for relative, (digest, length) in expected.items():
            recorded, _ = read_artifact_file(
                stage / relative, length, include_data=False,
            )
            if recorded != digest:
                raise PlatformReleaseRejected("offline staged delivery asset SHA-256 differs")
        # Do not let the original sealed ZIP change during the second pass.
        after_digest = _sealed_capsule_digest(capsule_path)
        if after_digest != capsule_digest:
            raise PlatformReleaseRejected("offline publisher capsule changed during review")
    except (KeyError, UnicodeError, zipfile.BadZipFile) as exc:
        raise PlatformReleaseRejected("offline capsule archive rejected") from exc

    inner = verify_offline_installer_bundle(
        root, trusted_public_key=key_path,
        trusted_key_sha256=trusted_key_sha256,
        trusted_signer_key_id=trusted_signer_key_id,
        expected_source_sha=expected_source_sha,
        expected_target=expected_target,
        minimum_revision=minimum_revision,
        expected_parent_manifest_sha256=expected_parent_manifest_sha256,
        require_local_host=require_local_host,
    )
    return {
        "schema": "aegis.installer.staged-double-signed-review.v1",
        "result": "OUTER_AND_INNER_SIGNED_BYTES_VERIFIED_ONLY",
        "capsule_sha256": capsule_digest,
        "delivery_index_sha256": sha256(signed_index).hexdigest(),
        "member_count": len(expected_names),
        "outer_publisher_signature_verified": True,
        "inner_release": inner.review(),
        "publisher_revocation_current_verified": False,
        "owner_approved": False,
        "install_executed": False,
        "native_service_registered": False,
        "service_health": "UNKNOWN",
        "core_activated": False,
        "fleet_enrolled": False,
    }
