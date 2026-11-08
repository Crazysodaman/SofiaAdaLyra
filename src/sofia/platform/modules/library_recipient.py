"""D028-02/04 recipient module preview over existing package signature verifier.

No new library wire format, publisher root, cache writer, Hub, transfer
service, OS installer or Core activation. A controls authenticated catalog
and peer scope; B supplies current publisher trust roots/revocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
from typing import Callable

from sofia.platform.modules.package import (
    SignedModuleManifest, VerifiedModulePackage, verify_module_package,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SOURCES = frozenset({
    "LOCAL_VERIFIED_CACHE", "OFFLINE_MEDIA", "OWNER_SELECTED_HUB",
    "AUTHORIZED_PEER", "OFFICIAL_REMOTE",
})
_LICENSES = frozenset({"permitted", "restricted", "non_redistributable", "unknown"})


class ModuleRecipientRejected(PermissionError):
    """Current signed artifact or source trust was not established."""


@dataclass(frozen=True, slots=True)
class ModuleRecipientPin:
    """Advisory reference from an independently verified signed catalog.

    This constructible object is not itself authenticated, does not grant
    publisher authority and is never a trusted installed/active receipt.
    """

    module_id: str
    version: str
    package_digest: str
    publisher: str
    trust_ref: str
    publisher_key_sha256: str
    source_kind: str
    license_distribution: str
    data_class: str
    catalog_revision: int
    metadata_fresh_until: datetime

    def __post_init__(self):
        if not isinstance(self.module_id, str) or not self.module_id:
            raise ModuleRecipientRejected("module ID required")
        if not isinstance(self.version, str) or not self.version:
            raise ModuleRecipientRejected("version required")
        for key in ("publisher", "trust_ref"):
            value = getattr(self, key)
            if not isinstance(value, str) or not 1 <= len(value) <= 200:
                raise ModuleRecipientRejected("publisher identity must be bounded")
        if (type(self.package_digest) is not str or _SHA.fullmatch(self.package_digest) is None
                or type(self.publisher_key_sha256) is not str
                or _SHA.fullmatch(self.publisher_key_sha256) is None):
            raise ModuleRecipientRejected("exact package and signer digests required")
        if self.source_kind not in _SOURCES:
            raise ModuleRecipientRejected("unknown source")
        if self.license_distribution not in _LICENSES:
            raise ModuleRecipientRejected("unknown license")
        if self.data_class not in {"public", "private"}:
            raise ModuleRecipientRejected("unknown data class")
        if type(self.catalog_revision) is not int or not 1 <= self.catalog_revision < 2**63:
            raise ModuleRecipientRejected("invalid catalog revision")
        if (not isinstance(self.metadata_fresh_until, datetime)
                or self.metadata_fresh_until.tzinfo is None
                or self.metadata_fresh_until.utcoffset() is None):
            raise ModuleRecipientRejected("aware catalog expiry required")


def review_signed_module_recipient(
    *,
    pin: ModuleRecipientPin,
    manifest: SignedModuleManifest,
    package_root: Path,
    now: datetime,
    catalog_revision_floor: int,
    catalog_admit: Callable[[ModuleRecipientPin], bool],
    publisher_key_lookup: Callable[[str], bytes],
    publisher_current: Callable[[str], bool],
    remote_source_current: Callable[[ModuleRecipientPin], bool] | None = None,
    internet_enabled: bool = False,
) -> VerifiedModulePackage:
    """Independently verify exact package bytes after current external admission.

    The caller MUST bind catalog_admit to Team A's signed index and current
    enrolled host/generation/STOP authority. Publisher roots/revocation MUST
    come from Team B's local trust policy, never a peer-provided key. This
    check is advisory: CAS admission, OS/ABI, installer approval, license
    authority and per-chunk STOP remain A/B service responsibilities.
    """
    if not isinstance(pin, ModuleRecipientPin) or not isinstance(manifest, SignedModuleManifest):
        raise ModuleRecipientRejected("canonical catalog pin and manifest required")
    if (not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or type(catalog_revision_floor) is not int or catalog_revision_floor < 0):
        raise ModuleRecipientRejected("trusted current clock/revision required")
    if now >= pin.metadata_fresh_until or pin.catalog_revision < catalog_revision_floor:
        raise ModuleRecipientRejected("catalog expired or rolled back")
    if pin.license_distribution == "unknown":
        raise ModuleRecipientRejected("unknown license cannot authorize acquisition")
    if pin.source_kind in {"OWNER_SELECTED_HUB", "AUTHORIZED_PEER"} and (
            pin.data_class != "public" or pin.license_distribution != "permitted"):
        raise ModuleRecipientRejected("license/private data forbids redistribution")
    if pin.source_kind == "OFFICIAL_REMOTE" and internet_enabled is not True:
        raise ModuleRecipientRejected("implicit Internet fallback forbidden")
    if pin.source_kind == "OFFLINE_MEDIA" and pin.data_class == "private":
        raise ModuleRecipientRejected("private media cannot enter shared package cache")
    if (not callable(catalog_admit) or not callable(publisher_key_lookup)
            or not callable(publisher_current)):
        raise ModuleRecipientRejected("canonical catalog and publisher trust required")
    # Denial must occur before any package read or publisher-key retrieval.
    if catalog_admit(pin) is not True:
        raise ModuleRecipientRejected("canonical signed catalog or host denied")
    if pin.source_kind in {"OWNER_SELECTED_HUB", "AUTHORIZED_PEER", "OFFICIAL_REMOTE"}:
        if remote_source_current is None or remote_source_current(pin) is not True:
            raise ModuleRecipientRejected("enrolled source not currently authorized")
    if publisher_current(pin.trust_ref) is not True:
        raise ModuleRecipientRejected("publisher revoked or untrusted")
    if (manifest.module_id != pin.module_id or manifest.version != pin.version
            or manifest.publisher != pin.publisher or manifest.trust_ref != pin.trust_ref
            or manifest.package_identity_digest() != pin.package_digest):
        raise ModuleRecipientRejected("signed package differs from pinned catalog")
    key = publisher_key_lookup(pin.trust_ref)
    if (type(key) is not bytes or len(key) != 32
            or sha256(key).hexdigest() != pin.publisher_key_sha256):
        raise ModuleRecipientRejected("independent publisher key pin mismatch")
    try:
        verified = verify_module_package(
            manifest, package_root=package_root, trusted_public_key=key,
        )
    except (ValueError, TypeError, OSError) as exc:
        raise ModuleRecipientRejected("recipient signature or file digest rejected") from exc
    if verified.package_digest != pin.package_digest:
        raise ModuleRecipientRejected("recipient package identity differs")
    return verified
