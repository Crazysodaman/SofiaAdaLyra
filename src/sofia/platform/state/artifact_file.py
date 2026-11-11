"""Bounded, identity-pinned artifact reads shared by release verifiers.

This does not grant access or execution authority. Callers verify signatures
and expected scope before observing the package root or calling this reader.
"""
from hashlib import sha256
import os
from pathlib import Path
import stat
from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.sdk.artifact import MAX_ARTIFACT_BYTES

def pinned_source_identity(details):
    """Metadata suitable for comparing a pathname stat with an open handle.

    Windows handle fstat may expose different file-ID/creation-time metadata
    than Path.stat on the same file. Do NOT mistake that OS difference for an
    attack. Windows still requires exact size, mtime, full signed byte hash
    and a post-read pathname check; POSIX additionally pins device/inode.
    """
    if os.name == "nt":
        return (details.st_size, details.st_mtime_ns)
    return (details.st_dev, details.st_ino, details.st_size,
            details.st_mtime_ns, details.st_ctime_ns)


class ArtifactFileRejected(PermissionError):
    pass

def read_artifact_file(path, size, *, include_data=False):
    if type(size) is not int or not 0 <= size <= MAX_ARTIFACT_BYTES:
        raise ArtifactFileRejected('artifact size outside the bounded contract')
    path = Path(path).absolute()
    assert_no_redirected_components(path, include_leaf=True)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_size != size:
        raise ArtifactFileRejected('artifact size/type differs')
    descriptor = os.open(path, os.O_RDONLY | getattr(os,'O_CLOEXEC',0) | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
    digest = sha256()
    pieces = [] if include_data else None
    with os.fdopen(descriptor,'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or pinned_source_identity(opened) != pinned_source_identity(before):
            raise ArtifactFileRejected('asset changed while opening')
        remaining = size
        while remaining:
            block = stream.read(min(remaining,65_536))
            if not block: raise ArtifactFileRejected('asset was truncated')
            digest.update(block)
            if pieces is not None: pieces.append(block)
            remaining -= len(block)
        if stream.read(1): raise ArtifactFileRejected('asset exceeded its signed bound')
        after = os.fstat(stream.fileno())
    assert_no_redirected_components(path, include_leaf=True)
    final = path.stat(follow_symlinks=False)
    if (pinned_source_identity(before) != pinned_source_identity(after)
            or pinned_source_identity(final) != pinned_source_identity(after)):
        raise ArtifactFileRejected('asset changed during verification')
    return digest.hexdigest(), None if pieces is None else b"".join(pieces)
