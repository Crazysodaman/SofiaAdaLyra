"""D028 efficient immutable B1 chunk source with tamper-detecting file identity.

An installed signer-verified artifact must be fully SHA256-checked by the
existing OfflineArtifactCache.resolve() ONCE at selection time, then rechecked
against its owner-private inode/size/mtime/ctime for every bounded chunk.
The actual chunk transport independently verifies fstat before and after its
64-KiB-block read. Do not rehash an 8-GiB blob 8192 times.

This is NOT an authorization, independent publisher signature, immutable-file
guarantee against a malicious filesystem owner, or a way to bypass B1 CAS.
Only a canonical Platform service with current SAFE and package revocation
may use it for read-only public signed chunks.
"""
from __future__ import annotations

from pathlib import Path
import stat

from sofia.platform.ops.library_chunk_receiver import (
    ChunkTransferRejected, PinnedChunkTransfer,
)
from sofia.platform.ops.platform_install import OfflineArtifactCache, PlatformArtifact
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
)


class VerifiedLibraryCacheSource:
    def __init__(
        self, *, cache: OfflineArtifactCache, artifact: PlatformArtifact,
    ) -> None:
        if not isinstance(cache, OfflineArtifactCache):
            raise TypeError("canonical B1 CAS required")
        if not isinstance(artifact, PlatformArtifact):
            raise TypeError("independent signed B1 artifact required")
        if artifact.signature_verified is not True:
            raise ChunkTransferRejected("unsigned B1 package cannot become a Hub source")
        cache._check_root()
        path = cache.resolve(artifact)
        if path != cache.root / artifact.sha256:
            raise ChunkTransferRejected("verified B1 cache source path mismatched")
        assert_no_redirected_components(path, include_leaf=True)
        assert_owner_private_path(path, directory=False)
        details = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                or not 1 <= details.st_size <= cache.max_bytes):
            raise ChunkTransferRejected("immutable B1 object identity unavailable")
        self.cache = cache
        self.artifact = artifact
        self.path = path
        self._identity = (
            details.st_dev, details.st_ino, details.st_size,
            details.st_mtime_ns, details.st_ctime_ns,
        )

    def current_path(self, transfer: PinnedChunkTransfer) -> Path:
        if (not isinstance(transfer, PinnedChunkTransfer)
                or transfer.content_sha256 != self.artifact.sha256
                or transfer.size_bytes != self._identity[2]
                or not self.artifact.signature_verified):
            raise ChunkTransferRejected("selected signed transfer differs from verified B1 source")
        self.cache._check_root()
        assert_no_redirected_components(self.path, include_leaf=True)
        assert_owner_private_path(self.path, directory=False)
        details = self.path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                or (details.st_dev, details.st_ino, details.st_size,
                    details.st_mtime_ns, details.st_ctime_ns) != self._identity):
            raise ChunkTransferRejected("B1 cache inode or content changed after signed selection")
        # Transport subsequently opens O_NOFOLLOW and fstats this exact inode,
        # checking for changes again AFTER each bounded chunk read.
        return self.path
