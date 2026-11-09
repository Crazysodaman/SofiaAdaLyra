"""D028 bounded sender-side reads from an independently verified local CAS.

Only the canonical Platform service may provide current auth and publisher
callbacks. This does not open a network port, enroll a peer or mint authority.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import stat
from typing import Callable

from sofia.platform.ops.library_chunk_receiver import (
    PinnedChunkTransfer, ChunkTransferRejected,
)

_MAX_CHUNK = 1024 * 1024


def read_authorized_cached_chunk(
    transfer: PinnedChunkTransfer, *, offset: int, length: int,
    authorize: Callable[[PinnedChunkTransfer], bool],
    publisher_current: Callable[[PinnedChunkTransfer], bool],
    resolve_verified_cache: Callable[[PinnedChunkTransfer], Path],
) -> tuple[bytes, str]:
    """Return one pinned chunk and its hash, never an install or signing grant.

    The service-owned resolve_verified_cache must use the existing signed
    release verifier + OfflineArtifactCache.resolve; network input cannot
    specify arbitrary filesystem paths.
    """
    if not isinstance(transfer, PinnedChunkTransfer):
        raise ChunkTransferRejected("typed signed-catalog transfer required")
    if (type(offset) is not int or type(length) is not int
            or offset < 0 or not 1 <= length <= _MAX_CHUNK
            or offset > transfer.size_bytes - length):
        raise ChunkTransferRejected("chunk offset/length outside signed content")
    if (not callable(authorize) or not callable(publisher_current)
            or not callable(resolve_verified_cache)):
        raise ChunkTransferRejected("service-owned authority and cache resolver required")

    def check_current():
        if authorize(transfer) is not True or publisher_current(transfer) is not True:
            raise ChunkTransferRejected(
                "current transfer grant or publisher verification unavailable"
            )

    check_current()
    path = resolve_verified_cache(transfer)
    if not isinstance(path, Path) or not path.is_absolute():
        raise ChunkTransferRejected("canonical verified CAS path required")
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_size != transfer.size_bytes):
        raise ChunkTransferRejected("verified cache source identity is unsafe")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_CLOEXEC", 0))
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
            raise ChunkTransferRejected("cache source changed while opening")
        os.lseek(fd, offset, os.SEEK_SET)
        chunks = []
        remaining = length
        while remaining:
            piece = os.read(fd, remaining)
            if not piece:
                raise ChunkTransferRejected("short read from verified cache")
            chunks.append(piece)
            remaining -= len(piece)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    final = path.lstat()
    if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise ChunkTransferRejected("verified cache source mutated during read")
    check_current()
    # Resolver is the canonical service's verified-inode snapshot, not a
    # remote path. Recheck AFTER byte read and the final SAFE/STOP checkpoint
    # so a replaced cached inode cannot be sent during an authorization race.
    again = resolve_verified_cache(transfer)
    if not isinstance(again, Path) or again != path:
        raise ChunkTransferRejected("canonical signed CAS path changed during transfer")
    rechecked = again.lstat()
    if (not stat.S_ISREG(rechecked.st_mode) or rechecked.st_nlink != 1
            or (rechecked.st_dev, rechecked.st_ino, rechecked.st_size,
                rechecked.st_mtime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_size,
                opened.st_mtime_ns)):
        raise ChunkTransferRejected("signed B1 cache source changed after chunk authorization")
    data = b"".join(chunks)
    return data, sha256(data).hexdigest()
