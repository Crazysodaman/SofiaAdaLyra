"""D028 authenticated-channel receiver for bounded immutable artifact chunks.

No network listener, publisher verification, owner grant, install or activation.
The canonical Platform service MUST authorize every chunk via authorize,
using its current SAFE/STOP, enrollment and generation authority. Only bytes
already bound to a separately trusted exact digest/size are accepted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import stat
from typing import Callable

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_MAX_CHUNK = 1024 * 1024
_MAX_TOTAL = 2**53 - 1


class ChunkTransferRejected(PermissionError):
    """A chunk is untrusted, stale, unsafe, or outside the pinned transfer."""


@dataclass(frozen=True, slots=True)
class PinnedChunkTransfer:
    source_platform_id: str
    target_platform_id: str
    content_sha256: str
    size_bytes: int
    generation: int

    def __post_init__(self) -> None:
        for identity in (self.source_platform_id, self.target_platform_id):
            if (type(identity) is not str or not 1 <= len(identity) <= 160
                    or not identity.isascii() or "/" in identity or "\\" in identity
                    or identity in {".", ".."}):
                raise ValueError("pinned platform identities required")
        if type(self.content_sha256) is not str or _DIGEST.fullmatch(self.content_sha256) is None:
            raise ValueError("exact lowercase SHA-256 required")
        if type(self.size_bytes) is not int or not 1 <= self.size_bytes <= _MAX_TOTAL:
            raise ValueError("positive bounded content size required")
        if type(self.generation) is not int or not 1 <= self.generation <= _MAX_TOTAL:
            raise ValueError("current bounded generation required")


class ChunkedArtifactReceiver:
    """Durable append-only incoming bytes; final CAS publication is NOT installation.

    Single-writer primitive to run inside the canonical Platform service.
    The service must serialize calls and bind authorize to a current grant.
    Signed publisher verification and B1 cache/installer controls remain required.
    """

    def __init__(self, root: Path | str, *, max_bytes: int) -> None:
        if type(max_bytes) is not int or not 1 <= max_bytes <= _MAX_TOTAL:
            raise ValueError("bounded transfer quota required")
        self.root = Path(root).absolute()
        self.max_bytes = max_bytes
        self._check_dir(self.root, create=True)
        self.incoming = self.root / "incoming"
        self.completed = self.root / "completed"
        self._check_dir(self.incoming, create=True)
        self._check_dir(self.completed, create=True)

    @staticmethod
    def _check_dir(path: Path, *, create: bool = False) -> None:
        if create:
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
        before = path.lstat()
        if not stat.S_ISDIR(before.st_mode) or stat.S_IMODE(before.st_mode) & 0o077:
            raise ChunkTransferRejected("artifact directory must be private and not redirected")

    def _check_roots(self) -> None:
        for directory in (self.root, self.incoming, self.completed):
            self._check_dir(directory)

    @staticmethod
    def _existing_file(path: Path) -> int:
        try:
            meta = path.lstat()
        except FileNotFoundError:
            return 0
        if (not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1
                or stat.S_IMODE(meta.st_mode) & 0o077):
            raise ChunkTransferRejected("incoming file is redirected, linked, or nonprivate")
        return meta.st_size

    @staticmethod
    def _approve(transfer: PinnedChunkTransfer, authorize: Callable[[PinnedChunkTransfer], bool]) -> None:
        if not isinstance(transfer, PinnedChunkTransfer) or not callable(authorize):
            raise ChunkTransferRejected("typed transfer and current authority required")
        if authorize(transfer) is not True:
            raise ChunkTransferRejected("current owner-enrolled SAFE grant unavailable")

    def received_bytes(self, transfer: PinnedChunkTransfer, *, authorize: Callable[[PinnedChunkTransfer], bool]) -> int:
        self._approve(transfer, authorize)
        self._check_roots()
        path = self.incoming / (transfer.content_sha256 + ".part")
        size = self._existing_file(path)
        if size > transfer.size_bytes:
            raise ChunkTransferRejected("incoming data exceeds pinned content size")
        return size

    def append_chunk(
        self, transfer: PinnedChunkTransfer, *, offset: int, chunk: bytes,
        chunk_sha256: str, authorize: Callable[[PinnedChunkTransfer], bool],
    ) -> int:
        self._approve(transfer, authorize)
        if (type(offset) is not int or offset < 0 or offset > _MAX_TOTAL
                or type(chunk) is not bytes or not 1 <= len(chunk) <= _MAX_CHUNK
                or type(chunk_sha256) is not str or _DIGEST.fullmatch(chunk_sha256) is None
                or sha256(chunk).hexdigest() != chunk_sha256):
            raise ChunkTransferRejected("invalid or corrupt bounded transfer chunk")
        if offset + len(chunk) > transfer.size_bytes or transfer.size_bytes > self.max_bytes:
            raise ChunkTransferRejected("transfer exceeds pinned size or quota")
        self._check_roots()
        path = self.incoming / (transfer.content_sha256 + ".part")
        if self._existing_file(self.completed / transfer.content_sha256):
            raise ChunkTransferRejected("complete object already published")
        current = self._existing_file(path)
        if current != offset:
            raise ChunkTransferRejected("non-sequential or stale resume cursor")
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or stat.S_IMODE(opened.st_mode) & 0o077
                    or opened.st_size != current):
                raise ChunkTransferRejected("incoming file identity changed")
            self._approve(transfer, authorize)
            with os.fdopen(fd, "wb", closefd=False) as writer:
                writer.write(chunk)
                writer.flush()
                os.fsync(fd)
            after = os.fstat(fd)
            if after.st_size != current + len(chunk):
                raise ChunkTransferRejected("transfer size changed during write")
        finally:
            os.close(fd)
        return current + len(chunk)

    def finalize(self, transfer: PinnedChunkTransfer, *, authorize: Callable[[PinnedChunkTransfer], bool]) -> Path:
        self._approve(transfer, authorize)
        self._check_roots()
        part = self.incoming / (transfer.content_sha256 + ".part")
        if self._existing_file(part) != transfer.size_bytes:
            raise ChunkTransferRejected("incomplete transfer cannot enter immutable store")
        digest = sha256()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        fd = os.open(part, flags)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != transfer.size_bytes:
                raise ChunkTransferRejected("incoming object changed")
            with os.fdopen(fd, "rb", closefd=False) as reader:
                while data := reader.read(65536):
                    digest.update(data)
            after = os.fstat(fd)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ChunkTransferRejected("incoming object mutated during verification")
        finally:
            os.close(fd)
        if digest.hexdigest() != transfer.content_sha256:
            raise ChunkTransferRejected("final content digest mismatch")
        self._approve(transfer, authorize)
        destination = self.completed / transfer.content_sha256
        if destination.exists() or destination.is_symlink():
            raise ChunkTransferRejected("immutable object already exists")
        os.link(part, destination, follow_symlinks=False)
        try:
            self._check_roots()
            published = destination.lstat()
            previous = part.lstat()
            if (not stat.S_ISREG(published.st_mode)
                    or (published.st_dev, published.st_ino) != (previous.st_dev, previous.st_ino)
                    or published.st_size != transfer.size_bytes
                    or published.st_nlink != 2):
                raise ChunkTransferRejected("published object failed identity check")
            part.unlink()
            if self._existing_file(destination) != transfer.size_bytes:
                raise ChunkTransferRejected("immutable object link count did not settle")
            # VERIFIED BYTES only. No publisher signature or install receipt.
            return destination
        except Exception:
            destination.unlink(missing_ok=True)
            raise
