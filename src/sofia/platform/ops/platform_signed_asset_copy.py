"""Stream publisher-signed Platform release assets into owner-private trees.

Shared by the ORIGINAL B1 staging and installation paths, never a second
release engine. Both callers first independently verify the signed manifest
and re-run the configured PlatformReleaseVerifier on the completed target
tree. This function copies one referenced artifact with bounded RAM and
rejects inode substitution, digest drift, truncation and redirected paths.

The input build asset need not be owner-private (it may be mounted read-only
media). The DESTINATION staging/installation tree is always owner-private.
No package approval, activation, signer enrollment or Core data is created.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat

from sofia.platform.ops.platform_release import PlatformReleaseRejected
from sofia.platform.state.artifact_file import read_artifact_file
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    ensure_owner_private_directory, restrict_new_owner_private_path,
)
from sofia.sdk.artifact import MAX_ARTIFACT_BYTES


def copy_verified_signed_asset(
    source: Path | str, destination: Path | str, *,
    expected_sha256: str, expected_size: int,
) -> Path:
    """Copy exactly one publisher-signed asset using at most 64KiB blocks.

    The expected SHA and exact byte length come from an independently
    authenticated canonical signed release manifest. Re-reading the final
    asset ensures no successful B1 receipt refers to unverified copied bytes.
    """
    if (type(expected_sha256) is not str or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)
            or type(expected_size) is not int
            or not 1 <= expected_size <= MAX_ARTIFACT_BYTES):
        raise PlatformReleaseRejected("bounded signed Platform asset reference required")
    src, dst = Path(source).absolute(), Path(destination).absolute()
    assert_no_redirected_components(src, include_leaf=True)
    assert_no_redirected_components(dst, include_leaf=True)
    before = src.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
        raise PlatformReleaseRejected("signed Platform source size or type changed")
    identity = (before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns)

    # Nonblocking reads prevent a racing FIFO substitution from hanging the
    # owner-controlled installer. O_NOFOLLOW is still required on POSIX.
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0))
    with os.fdopen(os.open(src, flags), "rb") as reader:
        opened = os.fstat(reader.fileno())
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino, opened.st_size,
                    opened.st_mtime_ns, opened.st_ctime_ns) != identity):
            raise PlatformReleaseRejected("signed Platform asset substituted before copy")
        ensure_owner_private_directory(dst.parent)
        assert_no_redirected_components(dst, include_leaf=True)
        dest_fd = os.open(
            dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        # If the source or output becomes invalid, clean up ONLY the new
        # destination after both handles close. No existing release is touched.
        try:
            with os.fdopen(dest_fd, "wb") as writer:
                restrict_new_owner_private_path(dst, directory=False)
                digest = sha256()
                remaining = expected_size
                while remaining:
                    chunk = reader.read(min(65536, remaining))
                    if not chunk:
                        raise PlatformReleaseRejected("signed Platform source truncated")
                    writer.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                if reader.read(1):
                    raise PlatformReleaseRejected("signed Platform source grew during copy")
                writer.flush()
                os.fsync(writer.fileno())
            after = os.fstat(reader.fileno())
            assert_no_redirected_components(src, include_leaf=True)
            final = src.stat(follow_symlinks=False)
            if (digest.hexdigest() != expected_sha256
                    or (after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns) != identity
                    or (final.st_dev, final.st_ino, final.st_size,
                        final.st_mtime_ns, final.st_ctime_ns) != identity):
                raise PlatformReleaseRejected("signed Platform source changed during copy")
            assert_owner_private_path(dst, directory=False)
            verified_sha256, _ = read_artifact_file(dst, expected_size)
            if verified_sha256 != expected_sha256:
                raise PlatformReleaseRejected("signed Platform destination changed after copy")
            return dst
        except BaseException:
            dst.unlink(missing_ok=True)
            raise
