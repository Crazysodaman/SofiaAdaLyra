"""D028-02/04 adapter for Team A's candidate signed Library catalog projection.

Pure review only. A owns authenticated broker/host enrollment and signed index,
B owns independently pinned publisher roots, actual archive verification and
its single cache/installer. This module creates neither authority nor bytes.
A strictly parsed JSON response alone is NEVER a signed catalog index.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re

from .compatibility import ModulePlatformTarget, evaluate_module_compatibility
from .package import OperationProfileKind, SignedModuleManifest, VerifiedModulePackage
from .library_recipient import (
    ModuleRecipientPin, ModuleRecipientRejected, review_signed_module_recipient,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DATA = frozenset({
    "catalog_revision", "catalog_generation", "catalog_fresh_until",
    "target_platform_id", "source", "page", "items",
})
_ITEM = frozenset({
    "artifact_id", "kind", "version", "revision", "manifest_digest",
    "content_digest", "size_bytes", "publisher", "signer_key_id",
    "signature_scheme", "signature_receipt_ref", "target_os_arch",
    "sdk_range", "abi_range", "license_distribution", "data_class",
    "distribution_allowed",
})
_SOURCE = frozenset({"kind", "source_id", "last_observed_at", "status"})
_PAGE = frozenset({"limit", "next_cursor", "cursor_state"})


def _exact(value: object, fields: frozenset[str]) -> Mapping[str, object]:
    if type(value) is not dict or set(value) != fields:
        raise ModuleRecipientRejected("unreviewed signed catalog fields")
    return value


def _timestamp(value: object) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 40:
        raise ModuleRecipientRejected("bounded catalog timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError("timezone")
        return result
    except ValueError as error:
        raise ModuleRecipientRejected("invalid catalog timestamp") from error


def _digest(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def review_selected_library_catalog_module(
    *,
    catalog_data: Mapping[str, object],
    selected_artifact_id: str,
    selected_manifest_digest: str,
    selected_content_digest: str,
    bound_platform_id: str,
    expected_catalog_generation: int,
    minimum_catalog_revision: int,
    manifest: SignedModuleManifest,
    package_root: Path,
    target: ModulePlatformTarget,
    now: datetime,
    profile: OperationProfileKind,
    verified_dependencies: tuple[VerifiedModulePackage, ...] = (),
    signed_index_admit: Callable[[Mapping[str, object]], bool],
    signed_content_admit: Callable[[Mapping[str, object], Path], bool],
    signer_binding_admit: Callable[[str, str], bool],
    os_sdk_abi_admit: Callable[[Mapping[str, object], ModulePlatformTarget], bool],
    catalog_admit: Callable[[ModuleRecipientPin], bool],
    publisher_key_lookup: Callable[[str], bytes],
    publisher_current: Callable[[str], bool],
    remote_source_current: Callable[[ModuleRecipientPin], bool] | None = None,
    internet_enabled: bool = False,
) -> VerifiedModulePackage:
    """Review exactly one selected signed module, with all external gates current.

    signed_index_admit must verify a publisher-signed index from A/B, not a
    Hub/peer JSON assertion. signed_content_admit must prove exact separately
    transferred archive SHA and signer/receipt via B's existing verifier.
    The other callbacks must bind A's current host/enrollment/SAFE and B's
    current key/identity/revocation. False, None and unavailable deny.
    """
    if (type(selected_artifact_id) is not str or not 1 <= len(selected_artifact_id) <= 160
            or not _digest(selected_manifest_digest)
            or not _digest(selected_content_digest)
            or type(bound_platform_id) is not str or not bound_platform_id
            or type(expected_catalog_generation) is not int
            or expected_catalog_generation < 1
            or type(minimum_catalog_revision) is not int
            or minimum_catalog_revision < 1
            or not isinstance(manifest, SignedModuleManifest)
            or not isinstance(target, ModulePlatformTarget)
            or not isinstance(profile, OperationProfileKind)
            or type(verified_dependencies) is not tuple
            or any(not isinstance(p, VerifiedModulePackage) for p in verified_dependencies)
            or not isinstance(now, datetime) or now.utcoffset() is None):
        raise ModuleRecipientRejected("exact selected identity, host and revision required")
    for gate in (signed_index_admit, signed_content_admit, signer_binding_admit,
                 os_sdk_abi_admit, catalog_admit, publisher_key_lookup,
                 publisher_current):
        if not callable(gate):
            raise ModuleRecipientRejected("current canonical trust gate missing")
    data = _exact(catalog_data, _DATA)
    revision = data["catalog_revision"]
    if (data["target_platform_id"] != bound_platform_id
            or type(revision) is not int or revision < minimum_catalog_revision
            or type(data["catalog_generation"]) is not int
            or data["catalog_generation"] != expected_catalog_generation):
        raise ModuleRecipientRejected("catalog target, revision or generation stale")
    source = _exact(data["source"], _SOURCE)
    page = _exact(data["page"], _PAGE)
    if (source["status"] != "CURRENT" or page["cursor_state"] != "CURRENT"
            or type(page["limit"]) is not int or not 1 <= page["limit"] <= 128
            or type(data["items"]) is not list
            or len(data["items"]) > page["limit"]):
        raise ModuleRecipientRejected("stale or unbounded catalog page")
    expiry = _timestamp(data["catalog_fresh_until"])
    if expiry <= now or _timestamp(source["last_observed_at"]) > now:
        raise ModuleRecipientRejected("catalog freshness expired or from future")
    # This independent signature gate MUST run before item selection or bytes.
    if signed_index_admit(data) is not True:
        raise ModuleRecipientRejected("publisher-signed index not verified")
    matches = []
    for candidate in data["items"]:
        row = _exact(candidate, _ITEM)
        if row["artifact_id"] == selected_artifact_id:
            matches.append(row)
    if len(matches) != 1:
        raise ModuleRecipientRejected("explicit selection missing or ambiguous")
    row = matches[0]
    if (row["kind"] != "module"
            or row["manifest_digest"] != selected_manifest_digest
            or row["content_digest"] != selected_content_digest
            or not _digest(row["manifest_digest"])
            or not _digest(row["content_digest"])
            or row["signature_scheme"] != "ed25519"
            or type(row["size_bytes"]) is not int
            or not 1 <= row["size_bytes"] <= 512 * 1024 * 1024
            or type(row["revision"]) is not int or row["revision"] < 1
            or type(row["signature_receipt_ref"]) is not str
            or not 1 <= len(row["signature_receipt_ref"]) <= 160
            or type(row["distribution_allowed"]) is not bool):
        raise ModuleRecipientRejected("selected content identity or signing metadata mismatched")
    if (row["license_distribution"] != "permitted"
            or row["data_class"] != "public") and row["distribution_allowed"]:
        raise ModuleRecipientRejected("private or restricted artifact illegally offered")
    if os_sdk_abi_admit(row, target) is not True:
        raise ModuleRecipientRejected("OS, SDK or ABI target incompatible")
    if manifest.package_identity_digest() != selected_manifest_digest:
        raise ModuleRecipientRejected("manifest differs from selected signed index")
    if signer_binding_admit(row["signer_key_id"], manifest.trust_ref) is not True:
        raise ModuleRecipientRejected("publisher signing key and trust root unbound")
    if signed_content_admit(row, package_root) is not True:
        raise ModuleRecipientRejected("archive digest or signed receipt not independently verified")
    if publisher_current(manifest.trust_ref) is not True:
        raise ModuleRecipientRejected("current publisher revocation denied")
    public_key = publisher_key_lookup(manifest.trust_ref)
    if type(public_key) is not bytes or len(public_key) != 32:
        raise ModuleRecipientRejected("independent publisher public key unavailable")
    pin = ModuleRecipientPin(
        module_id=manifest.module_id, version=row["version"],
        package_digest=selected_manifest_digest, publisher=row["publisher"],
        trust_ref=manifest.trust_ref,
        publisher_key_sha256=sha256(public_key).hexdigest(),
        source_kind=source["kind"], license_distribution=row["license_distribution"],
        data_class=row["data_class"], catalog_revision=revision,
        metadata_fresh_until=expiry,
    )
    verified = review_signed_module_recipient(
        pin=pin, manifest=manifest, package_root=package_root, now=now,
        catalog_revision_floor=minimum_catalog_revision,
        catalog_admit=catalog_admit, publisher_key_lookup=publisher_key_lookup,
        publisher_current=publisher_current,
        remote_source_current=remote_source_current,
        internet_enabled=internet_enabled,
    )
    # Use the existing canonical compatibility evaluator, never an invented
    # ABI parser; B/A approve exact OS/ABI in the external signed policy gate.
    report = evaluate_module_compatibility(
        verified.manifest, profile=profile, target=target,
        installed_dependencies=tuple(p.manifest for p in verified_dependencies),
    )
    if not report.compatible:
        raise ModuleRecipientRejected("signed module incompatible or dependency missing: "
                                      + "; ".join(report.reasons))
    return verified
