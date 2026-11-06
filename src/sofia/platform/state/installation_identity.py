"""Explicit Core-free installation identity bootstrap; no enrollment authority."""
from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from uuid import uuid4

from sofia.sdk.identity import AegisIdentity, IdentityKind
from sofia.platform.state.private_file import (
    assert_no_redirected_components, assert_owner_private_path,
    atomic_write_private_text, ensure_owner_private_directory,
    restrict_new_owner_private_path,
)

INSTALLATION_SCHEMA = "aegis.platform.installation.v1"
_DOMAIN = b"aegis.platform.installation.v1\x00"
_FIELDS = {"schema", "identity", "key_algorithm", "public_key_der", "created_at", "signature"}


class InstallationIdentityUnavailable(RuntimeError):
    """Identity is missing, unsafe or inconsistent; never silently regenerate it."""


def _canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate installation metadata key")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class InstallationIdentity:
    identity: AegisIdentity
    public_key_sha256: str
    created_at: datetime

    def to_payload(self) -> dict:
        """Public identity presentation, never credentials or permission."""
        return {
            "schema": INSTALLATION_SCHEMA,
            "identity": self.identity.to_payload(),
            "serial": self.identity.serial,
            "public_key_sha256": self.public_key_sha256,
            "created_at": self.created_at.isoformat(),
        }


class InstallationIdentityStore:
    """Own one immutable installation UUID/key binding in private local files.

    Bootstrap is explicit. Existing incomplete state is refused, not repaired.
    Neither a readable serial nor this local self-signature enrolls a peer or
    establishes owner authority. Existing Core identities are never opened.
    """

    def __init__(self, home: Path) -> None:
        if not isinstance(home, Path) or not home.is_absolute() or ".." in home.parts:
            raise ValueError("installation identity home must be an absolute unambiguous path")
        self.home = home
        self.metadata_path = home / "installation.json"
        self.key_path = home / "installation-key.pem"
        self._observed: tuple[str, str] | None = None

    @staticmethod
    def _private(path: Path, *, directory: bool) -> None:
        assert_owner_private_path(path, directory=directory)
        if os.name != "nt" and path.stat(follow_symlinks=False).st_uid != os.geteuid():
            raise PermissionError("installation identity belongs to another OS user")

    def _read(self, path: Path, limit: int) -> bytes:
        self._private(self.home, directory=True)
        self._private(path, directory=False)
        before = path.stat(follow_symlinks=False)
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise InstallationIdentityUnavailable("installation identity changed while opening")
            data = stream.read(limit + 1)
        self._private(self.home, directory=True)
        self._private(path, directory=False)
        after = path.stat(follow_symlinks=False)
        if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or len(data) > limit:
            raise InstallationIdentityUnavailable("installation identity changed or exceeded its bound")
        return data

    def load(self) -> InstallationIdentity:
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            raw = json.loads(self._read(self.metadata_path, 16_384), object_pairs_hook=_unique_object)
            if type(raw) is not dict or set(raw) != _FIELDS or raw["schema"] != INSTALLATION_SCHEMA:
                raise ValueError("unsupported installation identity schema")
            if raw["key_algorithm"] != "ed25519":
                raise ValueError("unsupported installation identity key")
            identity = AegisIdentity.from_payload(raw["identity"])
            if identity.kind is not IdentityKind.PLATFORM or identity.identity_id.int == 0:
                raise ValueError("a non-null Platform identity is required")
            key = serialization.load_pem_private_key(self._read(self.key_path, 4096), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("installation key must be Ed25519")
            public_der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            if b64decode(raw["public_key_der"], validate=True) != public_der:
                raise ValueError("installation identity key binding differs")
            signature = b64decode(raw["signature"], validate=True)
            body = {name: raw[name] for name in raw if name != "signature"}
            key.public_key().verify(signature, _DOMAIN + _canonical(body))
            created_at = datetime.fromisoformat(raw["created_at"])
            if created_at.tzinfo is None or created_at.utcoffset() is None:
                raise ValueError("installation creation time must be timezone-aware")
            fingerprint = sha256(public_der).hexdigest()
            observed = (identity.canonical_uuid, fingerprint)
            if self._observed is not None and self._observed != observed:
                raise ValueError("installation identity changed after opening")
            self._observed = observed
            return InstallationIdentity(identity, fingerprint, created_at.astimezone(timezone.utc))
        except InstallationIdentityUnavailable:
            raise
        except Exception as exc:
            raise InstallationIdentityUnavailable("installation identity is missing, unsafe or inconsistent; approved recovery is required") from exc

    def initialize(self) -> InstallationIdentity:
        """Explicit fresh initialization, or validate/reuse an existing identity."""
        assert_no_redirected_components(self.home, include_leaf=True)
        try:
            self.home.lstat()
        except FileNotFoundError:
            pass
        else:
            return self.load()
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        ensure_owner_private_directory(self.home.parent)
        try:
            self.home.mkdir(mode=0o700)
        except FileExistsError:
            return self.load()
        restrict_new_owner_private_path(self.home, directory=True)
        self._private(self.home, directory=True)
        # Only the exclusive directory creator allocates an identity/key.
        # Partial state is preserved on failure and subsequent init refuses it.
        identity = AegisIdentity(IdentityKind.PLATFORM, uuid4())
        key = Ed25519PrivateKey.generate()
        private_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()).decode("ascii")
        public_der = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        body = {
            "schema": INSTALLATION_SCHEMA, "identity": identity.to_payload(),
            "key_algorithm": "ed25519", "public_key_der": b64encode(public_der).decode("ascii"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        signature = b64encode(key.sign(_DOMAIN + _canonical(body))).decode("ascii")
        atomic_write_private_text(self.key_path, private_pem)
        atomic_write_private_text(self.metadata_path, _canonical({**body, "signature": signature}).decode("utf-8"))
        if os.name != "nt":
            for directory in (self.home, self.home.parent):
                descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        return self.load()


def configured_platform_identity_id() -> str:
    """Use explicit installation state when configured; retain legacy profiles."""
    home = os.environ.get("AEGIS_PLATFORM_IDENTITY_HOME", "").strip()
    explicit = os.environ.get("SOFIA_PLATFORM_INSTANCE_ID")
    if not home:
        return "platform:local" if explicit is None else explicit.strip()
    identity = InstallationIdentityStore(Path(home)).load().identity.canonical_uuid
    if explicit is not None and explicit.strip() != identity:
        raise InstallationIdentityUnavailable("configured Platform ID differs from immutable installation identity")
    return identity
