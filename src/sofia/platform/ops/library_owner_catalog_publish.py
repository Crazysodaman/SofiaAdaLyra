"""D028 owner-only LAN catalog publisher for one selected private Hub.

Private/personal-use model or voice files, unlicensed peer copies, credentials,
Core memory and arbitrary host files NEVER enter the advertised LAN catalog.
This produces only *publisher-signed metadata*, not an installation receipt
or an authorization for mTLS serving, peer enrollment, package activation or
public redistribution.

A canonical installed Platform supplies:
  * its exact source/target identities and current owner-approved Hub role;
  * selected B1 packages already verified under the independent signer root;
  * a fresh current publisher/root-revocation and owner STOP check;
  * an approved external Ed25519 signing callback, NEVER private key bytes.

No key generation, private key persistence, network bind, cache import or Hub
authorization occurs here. All output is independently verified with the
already pinned 32-byte public key before returning any signed index bytes.
"""
from __future__ import annotations

from base64 import b64encode
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from sofia.platform.ops.library_signed_index import (
    SCHEMA, _DOMAIN, verify_signed_library_index,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}\Z")
_SAFE = re.compile(r"[ -~]{1,160}\Z")
_MAX_SIGNED_BYTES = 65536
_MAX_ITEMS = 32
_MAX_EPOCH = 2**53 - 1


class OwnerCatalogPublishDenied(PermissionError):
    """Unsigned, unreviewed or nontransferable private LAN artifact."""


@dataclass(frozen=True, slots=True)
class OwnerPublishedAsset:
    """Exact B1 already-signed release identity, not raw arbitrary metadata."""

    artifact_id: str
    kind: str
    version: str
    revision: int
    manifest_digest: str
    content_digest: str
    size_bytes: int
    publisher: str
    signer_key_id: str
    signature_receipt_ref: str
    target_os_arch: str
    sdk_range: str
    abi_range: str
    license_distribution: str
    data_class: str
    distribution_allowed: bool
    independent_package_verified: bool

    def as_catalog_item(self) -> dict[str, object]:
        """Only independently signed PUBLIC and explicitly copyable payloads.

        A free noncommercial or personal-use license does not automatically
        authorize sending its weights to another machine. A no-copy model
        remains local even when it is lawful for the owner to run it.
        """
        for field in (
            "artifact_id", "kind", "version", "publisher", "signer_key_id",
            "signature_receipt_ref", "target_os_arch", "sdk_range", "abi_range",
        ):
            value = getattr(self, field)
            if type(value) is not str or _SAFE.fullmatch(value) is None:
                raise OwnerCatalogPublishDenied("bounded reviewed signed identity required")
        if self.kind not in {
            "platform_release", "sdk", "core_runtime", "core_definition",
            "module", "model", "asset", "rollback",
        }:
            raise OwnerCatalogPublishDenied("unknown signed artifact class")
        for field in ("manifest_digest", "content_digest"):
            value = getattr(self, field)
            if type(value) is not str or _SHA.fullmatch(value) is None:
                raise OwnerCatalogPublishDenied("publisher-signed manifest/content SHA required")
        if (type(self.revision) is not int
                or not 1 <= self.revision <= _MAX_EPOCH
                or type(self.size_bytes) is not int
                or not 1 <= self.size_bytes <= 8 * 1024**3
                or type(self.independent_package_verified) is not bool
                or self.independent_package_verified is not True
                or self.license_distribution != "permitted"
                or self.data_class != "public"
                or self.distribution_allowed is not True):
            raise OwnerCatalogPublishDenied(
                "personal-only/no-copy/protected/unsigned asset cannot be shared"
            )
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "version": self.version,
            "revision": self.revision,
            "manifest_digest": self.manifest_digest,
            "content_digest": self.content_digest,
            "size_bytes": self.size_bytes,
            "publisher": self.publisher,
            "signer_key_id": self.signer_key_id,
            "signature_scheme": "ed25519",
            "signature_receipt_ref": self.signature_receipt_ref,
            "target_os_arch": self.target_os_arch,
            "sdk_range": self.sdk_range,
            "abi_range": self.abi_range,
            "license_distribution": self.license_distribution,
            "data_class": self.data_class,
            "distribution_allowed": True,
        }


def publish_signed_owner_catalog(
    *, source_platform_id: str, target_platform_id: str,
    trusted_publisher_public_key: bytes,
    catalog_generation: int, catalog_revision: int,
    selected_assets: Sequence[OwnerPublishedAsset],
    sign_external: Callable[[bytes], bytes],
    owner_hub_current: Callable[[], bool],
    publisher_current: Callable[[str], bool],
    time_now: Callable[[], datetime],
    lifetime_seconds: int = 120,
) -> bytes:
    """Sign and self-verify a private single-owner source->recipient catalog.

    Installed service B1+Fleet integration must independently construct each
    OwnerPublishedAsset from its signed immutable manifests, release receipts
    and exact licensed-copy policy. This type is not an authority token and
    user-provided values must never be passed directly into this internal
    publisher API. The signer is called only after checking Hub/STOP, existing
    publisher root, selected target and transfer-license constraints.
    """
    if (type(source_platform_id) is not str or _ID.fullmatch(source_platform_id) is None
            or type(target_platform_id) is not str
            or _ID.fullmatch(target_platform_id) is None
            or source_platform_id == target_platform_id):
        raise OwnerCatalogPublishDenied("distinct owner-enrolled source and recipient required")
    if (type(trusted_publisher_public_key) is not bytes
            or len(trusted_publisher_public_key) != 32):
        raise OwnerCatalogPublishDenied("independently pinned Ed25519 public key required")
    for value in (catalog_generation, catalog_revision):
        if type(value) is not int or not 1 <= value <= _MAX_EPOCH:
            raise OwnerCatalogPublishDenied("current bounded signed catalog revision required")
    if (type(lifetime_seconds) is not int
            or not 30 <= lifetime_seconds <= 300
            or not isinstance(selected_assets, (tuple, list))
            or not 1 <= len(selected_assets) <= _MAX_ITEMS):
        raise OwnerCatalogPublishDenied("bounded personally selected catalog required")
    if not all(callable(v) for v in (
        sign_external, owner_hub_current, publisher_current, time_now,
    )):
        raise OwnerCatalogPublishDenied("current independent owner and signer authority required")
    key_hash = sha256(trusted_publisher_public_key).hexdigest()
    if (owner_hub_current() is not True
            or publisher_current(key_hash) is not True):
        raise OwnerCatalogPublishDenied("current owner Hub or publisher root denied")
    now = time_now()
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise OwnerCatalogPublishDenied("trusted service publication clock required")
    moment = now.astimezone(timezone.utc)
    items = []
    used: set[str] = set()
    for asset in selected_assets:
        if not isinstance(asset, OwnerPublishedAsset):
            raise OwnerCatalogPublishDenied("independently verified B1 artifact required")
        item = asset.as_catalog_item()
        if item["artifact_id"] in used:
            raise OwnerCatalogPublishDenied("ambiguous duplicate selected artifact")
        used.add(item["artifact_id"])
        if item["revision"] > catalog_revision:
            raise OwnerCatalogPublishDenied("artifact revision exceeds signed catalog")
        items.append(item)
    items.sort(key=lambda item: item["artifact_id"])
    issued = moment.isoformat()
    expires = (moment + timedelta(seconds=lifetime_seconds)).isoformat()
    fresh_until = (moment + timedelta(seconds=lifetime_seconds - 10)).isoformat()
    doc = {
        "schema": SCHEMA,
        "publisher_key_sha256": key_hash,
        "source_platform_id": source_platform_id,
        "target_platform_id": target_platform_id,
        "catalog_revision": catalog_revision,
        "catalog_generation": catalog_generation,
        "issued_at": issued,
        "expires_at": expires,
        "catalog": {
            "catalog_revision": catalog_revision,
            "catalog_generation": catalog_generation,
            "catalog_fresh_until": fresh_until,
            "target_platform_id": target_platform_id,
            "source": {
                "kind": "OWNER_SELECTED_HUB",
                "source_id": source_platform_id,
                "last_observed_at": issued,
                "status": "CURRENT",
            },
            "page": {
                "limit": _MAX_ITEMS, "next_cursor": None,
                "cursor_state": "CURRENT",
            },
            "items": items,
        },
    }
    canonical = json.dumps(
        doc, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    # A signer is an external trusted service interface. Never accept its
    # unverified "OK" response or private key material as a trust anchor.
    if owner_hub_current() is not True or publisher_current(key_hash) is not True:
        raise OwnerCatalogPublishDenied("owner Hub or publisher revoked before signing")
    signature = sign_external(_DOMAIN + canonical)
    if type(signature) is not bytes or len(signature) != 64:
        raise OwnerCatalogPublishDenied("external Ed25519 signer returned invalid detached signature")
    output = json.dumps(
        {**doc, "signature_b64": b64encode(signature).decode("ascii")},
        sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    if not 1 <= len(output) <= _MAX_SIGNED_BYTES:
        raise OwnerCatalogPublishDenied("publisher catalog exceeds signed wire bound")
    verified = verify_signed_library_index(
        output,
        trusted_publisher_public_key=trusted_publisher_public_key,
        expected_publisher_key_sha256=key_hash,
        expected_source_platform_id=source_platform_id,
        expected_target_platform_id=target_platform_id,
        expected_catalog_generation=catalog_generation,
        minimum_catalog_revision=catalog_revision,
        now=moment,
        publisher_key_current=publisher_current,
    )
    if (verified.catalog["items"] != items
            or not verified.matches(verified.catalog)
            or owner_hub_current() is not True
            or publisher_current(key_hash) is not True):
        raise OwnerCatalogPublishDenied("signed owner catalog changed or authority revoked")
    return output
