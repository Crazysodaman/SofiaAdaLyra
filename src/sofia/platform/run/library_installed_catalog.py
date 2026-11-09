"""D028 installed, owner-private signed catalog source for canonical IPC.

The profile is a FILE SOURCE, never a trust root. The canonical B1 installation
and owner Fleet enrollment must independently supply the expected publisher
public-key SHA-256, selected source Platform ID, recipient Platform ID,
catalog generation and rollback floor. A malicious profile cannot supply any
of those values or self-enroll by embedding its own public key.

Reads are bounded and inode-pinned, reject redirected/hardlinked/nonprivate
files, and reverify publisher signature and revocation every time. No file is
created, no signer key is minted, no Hub started and no listener added.
"""
from __future__ import annotations

from base64 import b64decode
from binascii import Error as Base64Error
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from typing import Callable

from sofia.platform.ops.library_signed_index import (
    verify_signed_library_index,
)
from sofia.platform.run.library_read_dispatch import InstalledSignedCatalogSource
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
)

_PROFILE_SCHEMA = "aegis.platform.library.installed-catalog-profile.v1"
_PROFILE_KEYS = frozenset({
    "schema", "signed_index_b64", "publisher_public_key_b64",
})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_PROFILE_BYTES = 128 * 1024


def _unique(items):
    data = {}
    for key, value in items:
        if key in data:
            raise PermissionError("duplicate installed Library profile property")
        data[key] = value
    return data


def _read_private_profile(path: Path) -> bytes:
    assert_no_redirected_components(path, include_leaf=True)
    assert_owner_private_path(path.parent, directory=True)
    assert_owner_private_path(path, directory=False)
    first = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(first.st_mode) or first.st_nlink != 1
            or not 1 <= first.st_size <= _MAX_PROFILE_BYTES):
        raise PermissionError("bounded single-inode installed Library profile required")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (first.st_dev, first.st_ino, first.st_size, first.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            raise PermissionError("Library catalog profile changed while opening")
        data = bytearray()
        with os.fdopen(descriptor, "rb", closefd=False) as reader:
            while len(data) <= _MAX_PROFILE_BYTES:
                block = reader.read(min(65536, _MAX_PROFILE_BYTES + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
        if len(data) != first.st_size:
            raise PermissionError("Library catalog profile changed length")
        after = os.fstat(descriptor)
        assert_no_redirected_components(path, include_leaf=True)
        final = path.stat(follow_symlinks=False)
        identity = (first.st_dev, first.st_ino, first.st_size, first.st_mtime_ns)
        if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or identity != (
            final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns
        ):
            raise PermissionError("Library catalog profile changed during verification")
        return bytes(data)
    finally:
        os.close(descriptor)


class InstalledLibraryCatalogProvider:
    """Only canonical B1+Fleet service composition may instantiate this."""

    def __init__(
        self, *, profile: Path | str,
        expected_publisher_key_sha256: str,
        expected_source_platform_id: str,
        expected_target_platform_id: str,
        expected_catalog_generation: int,
        minimum_catalog_revision: int,
        publisher_key_current: Callable[[str], bool],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        path = Path(profile).absolute()
        assert_no_redirected_components(path, include_leaf=True)
        if (type(expected_publisher_key_sha256) is not str
                or _SHA.fullmatch(expected_publisher_key_sha256) is None):
            raise PermissionError("independently pinned B1 signing key required")
        for value in (expected_source_platform_id, expected_target_platform_id):
            if type(value) is not str or not value or len(value) > 160:
                raise PermissionError("explicit enrolled source and installed target required")
        for value in (expected_catalog_generation, minimum_catalog_revision):
            if type(value) is not int or not 1 <= value < 2**53:
                raise PermissionError("explicit current catalog generation and rollback floor required")
        if not callable(publisher_key_current):
            raise PermissionError("live publisher revocation authority required")
        self.path = path
        self.key_sha256 = expected_publisher_key_sha256
        self.source_id = expected_source_platform_id
        self.target_id = expected_target_platform_id
        self.generation = expected_catalog_generation
        self.floor = minimum_catalog_revision
        self.current = publisher_key_current
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def __call__(self) -> InstalledSignedCatalogSource:
        raw = _read_private_profile(self.path)
        try:
            fields = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(
                    PermissionError("nonfinite Library installed profile value")
                ),
            )
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise PermissionError("invalid installed Library profile JSON") from exc
        if (type(fields) is not dict or set(fields) != _PROFILE_KEYS
                or fields["schema"] != _PROFILE_SCHEMA):
            raise PermissionError("unreviewed installed Library profile envelope")
        for key in ("signed_index_b64", "publisher_public_key_b64"):
            if (type(fields[key]) is not str
                    or len(fields[key]) > _MAX_PROFILE_BYTES):
                raise PermissionError("bounded installed Library profile field required")
        try:
            signed_index = b64decode(fields["signed_index_b64"], validate=True)
            public_key = b64decode(fields["publisher_public_key_b64"], validate=True)
        except (ValueError, Base64Error) as exc:
            raise PermissionError("invalid installed Library profile encoding") from exc
        if (len(public_key) != 32
                or sha256(public_key).hexdigest() != self.key_sha256):
            raise PermissionError("profile publisher key differs from independent installed B1 root")
        now = self.clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise PermissionError("trusted installed Library clock required")
        verify_signed_library_index(
            signed_index,
            trusted_publisher_public_key=public_key,
            expected_publisher_key_sha256=self.key_sha256,
            expected_source_platform_id=self.source_id,
            expected_target_platform_id=self.target_id,
            expected_catalog_generation=self.generation,
            minimum_catalog_revision=self.floor,
            now=now, publisher_key_current=self.current,
        )
        return InstalledSignedCatalogSource(
            raw_signed_index=signed_index,
            trusted_publisher_public_key=public_key,
            expected_publisher_key_sha256=self.key_sha256,
            expected_source_platform_id=self.source_id,
            expected_catalog_generation=self.generation,
            minimum_catalog_revision=self.floor,
            publisher_key_current=self.current,
        )
