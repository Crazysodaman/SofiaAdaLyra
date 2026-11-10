"""D028 authenticated-channel receiver for bounded immutable artifact chunks.

No network listener, publisher verification, owner grant, install or activation.
The canonical Platform service MUST authorize every chunk via authorize,
using its current SAFE/STOP, enrollment and generation authority. Only bytes
already bound to a separately trusted exact digest/size are accepted here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable

from sofia.platform.state.private_file import assert_no_redirected_components
from sofia.platform.run.process_lock import StateProcessLock

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PEER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}\Z")
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
    manifest_sha256: str
    catalog_revision: int
    artifact_kind: str
    license_distribution: str
    data_class: str

    def __post_init__(self) -> None:
        for identity in (self.source_platform_id, self.target_platform_id):
            if type(identity) is not str or _PEER_ID.fullmatch(identity) is None:
                raise ValueError("pinned platform identities required")
        if type(self.content_sha256) is not str or _DIGEST.fullmatch(self.content_sha256) is None:
            raise ValueError("exact lowercase SHA-256 required")
        if (type(self.manifest_sha256) is not str
                or _DIGEST.fullmatch(self.manifest_sha256) is None):
            raise ValueError("signed manifest SHA-256 pin required")
        if type(self.catalog_revision) is not int or not 1 <= self.catalog_revision <= _MAX_TOTAL:
            raise ValueError("positive signed catalog revision required")
        if self.artifact_kind not in {
            "platform_release", "sdk", "core_runtime", "core_definition",
            "module", "model", "asset", "rollback",
        }:
            raise ValueError("reviewed artifact class required")
        if self.license_distribution != "permitted" or self.data_class != "public":
            raise ValueError("protected or non-distributable artifact must not transfer")
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
        # Check every ancestor BEFORE creating any file, not only the leaf.
        assert_no_redirected_components(path, include_leaf=True)
        if create:
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
        before = path.lstat()
        if not stat.S_ISDIR(before.st_mode) or stat.S_IMODE(before.st_mode) & 0o077:
            raise ChunkTransferRejected("artifact directory must be private and not redirected")

    def _check_roots(self) -> None:
        for parent in (self.root, *self.root.parents):
            if parent.is_symlink():
                raise ChunkTransferRejected("artifact ancestor directory is redirected")
        for directory in (self.root, self.incoming, self.completed):
            self._check_dir(directory)

    @staticmethod
    def _scope_bytes(transfer: PinnedChunkTransfer) -> bytes:
        """Complete durable grant context, not merely matching content SHA."""
        data = json.dumps(
            {"schema": "aegis.library.incoming-scope.v1",
             "transfer": asdict(transfer)},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        if not 1 <= len(data) <= 2048:
            raise ChunkTransferRejected("bounded durable transfer provenance required")
        return data

    def _scope_path(self, transfer: PinnedChunkTransfer) -> Path:
        return self.incoming / (transfer.content_sha256 + ".scope")

    def _check_scope(
        self, transfer: PinnedChunkTransfer, *,
        part_size: int, allow_create: bool,
    ) -> None:
        """Bind exact source, target, signed manifest, revision, epoch and size.

        Single writer is owned by the canonical Platform. A metadata file
        cannot retroactively endorse pre-existing orphan partial bytes.
        """
        expected = self._scope_bytes(transfer)
        path = self._scope_path(transfer)
        assert_no_redirected_components(path, include_leaf=True)
        try:
            before = path.lstat()
        except FileNotFoundError:
            if part_size != 0:
                raise ChunkTransferRejected("unbound legacy partial transfer refused")
            if not allow_create:
                return
            flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_CLOEXEC", 0))
            fd = os.open(path, flags, 0o600)
            try:
                with os.fdopen(fd, "wb", closefd=False) as writer:
                    writer.write(expected)
                    writer.flush()
                    os.fsync(fd)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            finally:
                os.close(fd)
            # Persist the metadata directory entry BEFORE the first .part
            # write so a crash cannot leave bytes with no bound provenance.
            if os.name != "nt":
                directory = os.open(
                    self.incoming,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                )
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            before = path.lstat()
        if (not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or stat.S_IMODE(before.st_mode) & 0o077
                or before.st_size != len(expected)):
            raise ChunkTransferRejected("unsafe or changed durable transfer scope")
        fd = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            opened = os.fstat(fd)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (opened.st_dev, opened.st_ino,
                        opened.st_size, opened.st_mtime_ns)):
                raise ChunkTransferRejected("durable scope replaced during open")
            with os.fdopen(fd, "rb", closefd=False) as reader:
                recorded = reader.read(len(expected) + 1)
            after = os.fstat(fd)
            final = path.lstat()
            expected_identity = (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
            )
            if (recorded != expected
                    or (after.st_dev, after.st_ino,
                        after.st_size, after.st_mtime_ns) != expected_identity
                    or (final.st_dev, final.st_ino,
                        final.st_size, final.st_mtime_ns) != expected_identity):
                raise ChunkTransferRejected("durable transfer scope differs from signed pinned plan")
        finally:
            os.close(fd)

    def _writer_lock(self) -> StateProcessLock:
        """One OS-backed nonblocking writer per quarantine across processes.

        Content digests never create lock keys: the exact owner-private
        destination root determines the lock. A crashed process releases
        the OS lock, but the durable pinned .scope remains for safe resume.
        """
        self._check_roots()
        return StateProcessLock(
            self.root / "library-receiver",
            resource="library-receiver",
            lock_directory=self.root,
        )

    def _used_bytes(self) -> int:
        """Count all incoming and completed bytes, not each transfer separately."""
        total = 0
        count = 0
        for directory in (self.incoming, self.completed):
            for path in directory.iterdir():
                count += 1
                if count > 10000:
                    raise ChunkTransferRejected("too many store objects to review")
                recorded = self._existing_file(path)
                # Metadata is small and independently bounded; quota counts
                # transferred bytes, not private plan serialization overhead.
                if directory == self.incoming and path.name.endswith(".scope"):
                    if (_DIGEST.fullmatch(path.name.removesuffix(".scope")) is None
                            or recorded == 0 or recorded > 2048):
                        raise ChunkTransferRejected("unexpected transfer scope metadata")
                    continue
                if directory == self.incoming:
                    if (not path.name.endswith(".part")
                            or _DIGEST.fullmatch(path.name.removesuffix(".part")) is None):
                        raise ChunkTransferRejected("unexpected quarantine object")
                elif _DIGEST.fullmatch(path.name) is None:
                    raise ChunkTransferRejected("unexpected completed CAS object")
                total += recorded
                if total > self.max_bytes:
                    raise ChunkTransferRejected("aggregate verified and incoming quota exceeded")
        return total

    @staticmethod
    def _existing_file(path: Path) -> int:
        try:
            assert_no_redirected_components(path, include_leaf=True)
        except PermissionError as exc:
            raise ChunkTransferRejected("incoming path contains a redirected component") from exc
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
        with self._writer_lock():
            self._approve(transfer, authorize)
            self._check_roots()
            path = self.incoming / (transfer.content_sha256 + ".part")
            size = self._existing_file(path)
            self._check_scope(transfer, part_size=size, allow_create=False)
            if size > transfer.size_bytes:
                raise ChunkTransferRejected("incoming data exceeds pinned content size")
            return size

    def append_chunk(
        self, transfer: PinnedChunkTransfer, *, offset: int, chunk: bytes,
        chunk_sha256: str, authorize: Callable[[PinnedChunkTransfer], bool],
    ) -> int:
        with self._writer_lock():
            self._approve(transfer, authorize)
            if (type(offset) is not int or offset < 0 or offset > _MAX_TOTAL
                    or type(chunk) is not bytes or not 1 <= len(chunk) <= _MAX_CHUNK
                    or type(chunk_sha256) is not str or _DIGEST.fullmatch(chunk_sha256) is None
                    or sha256(chunk).hexdigest() != chunk_sha256):
                raise ChunkTransferRejected("invalid or corrupt bounded transfer chunk")
            if offset + len(chunk) > transfer.size_bytes or transfer.size_bytes > self.max_bytes:
                raise ChunkTransferRejected("transfer exceeds pinned size or quota")
            self._check_roots()
            if self._used_bytes() + len(chunk) > self.max_bytes:
                raise ChunkTransferRejected("aggregate transfer quota exceeded")
            path = self.incoming / (transfer.content_sha256 + ".part")
            if self._existing_file(self.completed / transfer.content_sha256):
                raise ChunkTransferRejected("complete object already published")
            current = self._existing_file(path)
            if current != offset:
                raise ChunkTransferRejected("non-sequential or stale resume cursor")
            self._check_scope(transfer, part_size=current, allow_create=True)
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
                if current == 0 and os.name != "nt":
                    # First .part directory entry must be durable before the
                    # sender receives a resumable offset or progress receipt.
                    directory = os.open(
                        self.incoming,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                    )
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                self._check_scope(
                    transfer, part_size=current + len(chunk), allow_create=False,
                )
                try:
                    self._approve(transfer, authorize)  # STOP/revoke during write denies chunk
                except Exception:
                    os.ftruncate(fd, current)
                    os.fsync(fd)
                    raise
            finally:
                os.close(fd)
            return current + len(chunk)

    def recover_interrupted_publication(
        self, transfer: PinnedChunkTransfer, *,
        authorize: Callable[[PinnedChunkTransfer], bool],
    ) -> Path:
        """Resume a crash after CAS link and before scope cleanup.

        Caller must independently reauthorize under current SAFE/STOP. A
        completed file is never an installer receipt or publisher signature.
        The originally durable exact transfer scope is still required.
        """
        with self._writer_lock():
            self._approve(transfer, authorize)
            self._check_roots()
            part = self.incoming / (transfer.content_sha256 + ".part")
            complete = self.completed / transfer.content_sha256
            if self._existing_file(part):
                raise ChunkTransferRejected(
                    "pending partial transfer requires ordinary finalize"
                )
            self._check_scope(
                transfer, part_size=0, allow_create=False,
            )
            scope = self._scope_path(transfer)
            if not scope.is_file():
                raise ChunkTransferRejected(
                    "unbound completed CAS cannot be adopted"
                )
            if self._existing_file(complete) != transfer.size_bytes:
                raise ChunkTransferRejected(
                    "no exact completed object to recover"
                )
            # Rehash the whole verified CAS, not just its filename: an inode
            # left behind by a crash does not prove final SHA or publisher.
            flags = (
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            descriptor = os.open(complete, flags)
            digest = sha256()
            try:
                before = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size != transfer.size_bytes
                ):
                    raise ChunkTransferRejected("unsafe recovered CAS inode")
                with os.fdopen(descriptor, "rb", closefd=False) as reader:
                    while block := reader.read(65536):
                        digest.update(block)
                after = os.fstat(descriptor)
                if (
                    (before.st_dev, before.st_ino, before.st_size,
                     before.st_mtime_ns, before.st_ctime_ns)
                    != (after.st_dev, after.st_ino, after.st_size,
                        after.st_mtime_ns, after.st_ctime_ns)
                    or digest.hexdigest() != transfer.content_sha256
                ):
                    raise ChunkTransferRejected(
                        "interrupted CAS publication content changed"
                    )
            finally:
                os.close(descriptor)
            self._approve(transfer, authorize)
            self._check_scope(
                transfer, part_size=0, allow_create=False,
            )
            scope.unlink()
            if os.name != "nt":
                directory = os.open(
                    self.incoming,
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                )
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            return complete

    def finalize(self, transfer: PinnedChunkTransfer, *, authorize: Callable[[PinnedChunkTransfer], bool]) -> Path:
        with self._writer_lock():
            self._approve(transfer, authorize)
            self._check_roots()
            part = self.incoming / (transfer.content_sha256 + ".part")
            if self._existing_file(part) != transfer.size_bytes:
                raise ChunkTransferRejected("incomplete transfer cannot enter immutable store")
            self._check_scope(
                transfer, part_size=transfer.size_bytes, allow_create=False,
            )
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
            # The published file must be the *same inode* whose bytes passed SHA-256.
            # A same-size replacement after hash verification is still untrusted.
            verified_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            if digest.hexdigest() != transfer.content_sha256:
                raise ChunkTransferRejected("final content digest mismatch")
            self._approve(transfer, authorize)
            destination = self.completed / transfer.content_sha256
            if destination.exists() or destination.is_symlink():
                raise ChunkTransferRejected("immutable object already exists")
            # Do not destroy the only verified copy after partial unlink:
            # failure in the final fsync/scope cleanup is recoverable using
            # recover_interrupted_publication() and the same signed plan.
            removed_partial = False
            try:
                self._check_roots()
                published = destination.lstat()
                previous = part.lstat()
                if (not stat.S_ISREG(published.st_mode)
                        or (published.st_dev, published.st_ino)
                           != (previous.st_dev, previous.st_ino)
                        or published.st_size != transfer.size_bytes
                        or (published.st_dev, published.st_ino, published.st_size,
                            published.st_mtime_ns) != verified_identity
                        or published.st_nlink != 2):
                    raise ChunkTransferRejected("published object failed identity check")
                self._check_scope(
                    transfer, part_size=transfer.size_bytes,
                    allow_create=False,
                )
                self._approve(transfer, authorize)
                if os.name != "nt":
                    directory = os.open(
                        self.completed,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                    )
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                part.unlink()
                removed_partial = True
                if self._existing_file(destination) != transfer.size_bytes:
                    raise ChunkTransferRejected("immutable object link count did not settle")
                self._check_scope(transfer, part_size=0, allow_create=False)
                self._scope_path(transfer).unlink()
                if os.name != "nt":
                    directory = os.open(
                        self.incoming,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                    )
                    try:
                        os.fsync(directory)
                    finally:
                        os.close(directory)
                # Digest verified bytes only; publisher and B1 approval remain separate.
                return destination
            except BaseException as exc:
                if not removed_partial:
                    destination.unlink(missing_ok=True)
                    raise
                raise RuntimeError(
                    "CAS OUTCOME_UNKNOWN: full bytes retained; recover using "
                    "original signed transfer and current SAFE authority"
                ) from exc

