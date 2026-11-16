"""Deterministic, offline, *test-signed* Aegis Platform release assembler.

This tool reuses the existing canonical release contracts and producers:

* component wheels come from :mod:`sofia.platform.verify.component_artifacts`;
* bundled CPython comes from :mod:`sofia.platform.verify.python_runtime`;
* native bytes are checked by :mod:`sofia.platform.verify.native_artifact`;
* the manifest is the existing :class:`sofia.sdk.platform_release.PlatformReleaseManifest`;
* the finished bundle is re-verified by
  :class:`sofia.platform.ops.platform_release.PlatformReleaseVerifier`.

It never signs with a production key, never writes a trust root, never installs,
and never claims an installed-host result.  The caller supplies a disposable
Ed25519 key; the private key and public key are never copied into the output.
"""
from __future__ import annotations

import argparse
from base64 import b64encode
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform as host_platform
import re
import shutil
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT / "src"))
    sys.path.insert(0, str(_ROOT))

from cryptography.hazmat.primitives import serialization  # noqa: E402

from sofia.platform.dev.release_signing import load_ed25519_private_key  # noqa: E402
from sofia.platform.ops.platform_release import PlatformReleaseVerifier  # noqa: E402
from sofia.platform.verify.component_artifacts import (  # noqa: E402
    ComponentArtifactError, build_component, inspect_wheel,
)
from sofia.platform.verify.native_artifact import verify_native_target  # noqa: E402
from sofia.platform.verify.python_runtime import (  # noqa: E402
    build_python_runtime, verify_python_runtime,
)
from sofia.sdk.artifact import ArtifactReference, validate_artifact_path  # noqa: E402
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION  # noqa: E402
from sofia.sdk.platform_release import (  # noqa: E402
    PlatformReleaseAsset, PlatformReleaseManifest, PlatformReleaseTarget,
)

SCHEMA_RECEIPT = "aegis.platform.release-assembly.v1"
SCHEMA_DIGESTS = "aegis.platform.release-artifact-digests.v1"
SCHEMA_PROVENANCE = "aegis.platform.release-assembly-provenance.v1"
SCHEMA_INVENTORY = "aegis.platform.release-dependency-inventory.v1"
SCHEMA_SBOM = "aegis.platform.release-sbom.v1"

REQUIRED_KINDS = frozenset({
    "sdk", "platform", "service", "python-runtime",
    "dependency-lock", "sbom", "provenance",
})

_GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PYTHON_VERSION = re.compile(r"3\.12\.(?:0|[1-9][0-9]{0,4})\Z")
_RELEASE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\Z")

_CORE_MARKERS = ("sofia/core/", "sofia-core", "sofia_core")
_PII_WHEEL_SUFFIXES = (".db", ".sqlite", ".sqlite3")
_ASSET_PII_MARKERS = (
    "sofia.db", "core-identity", "core_identity", "owner-secret",
    "owner_secret", "private-key", "private_key",
)
_NATIVE_NAMES = {
    PlatformReleaseTarget.WINDOWS_X86_64: {
        "service": ("aegis-platform-service.exe",),
        "tui": ("aegis_tui.exe", "aegis-tui.exe"),
    },
    PlatformReleaseTarget.DEBIAN12_X86_64: {
        "service": ("aegis-platform-service",),
        "tui": ("aegis_tui", "aegis-tui"),
    },
}


class ReleaseAssemblyError(RuntimeError):
    """Raised when an input cannot produce a complete, honest release bundle."""


def _json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_read(path: Path, limit: int = 512 * 1024**2) -> bytes:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ReleaseAssemblyError(f"release input is not a regular file: {path}")
    size = path.stat().st_size
    if not 1 <= size <= limit:
        raise ReleaseAssemblyError(f"release input is outside bounded size: {path}")
    return path.read_bytes()


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", *arguments],
        cwd=str(repo), capture_output=True, text=True, timeout=30,
    )
    if completed.returncode != 0:
        raise ReleaseAssemblyError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def resolve_source_state(
    repo: Path, expected_sha: str, *, allow_dirty: bool,
) -> tuple[str, bool, datetime]:
    """Bind the bundle to the exact clean checkout, or refuse."""
    repo = Path(repo).absolute()
    if not _GIT_SHA.fullmatch(expected_sha or ""):
        raise ReleaseAssemblyError("exact lowercase 40-hex source SHA required")
    top = Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if top != repo.resolve():
        raise ReleaseAssemblyError("--repo must be the exact checkout root")
    observed = _git(repo, "rev-parse", "HEAD")
    if observed != expected_sha:
        raise ReleaseAssemblyError(
            f"source SHA mismatch: requested {expected_sha}, checkout {observed}"
        )
    dirty = _git(repo, "status", "--porcelain", "--untracked-files=normal")
    clean = not dirty
    if not clean and not allow_dirty:
        raise ReleaseAssemblyError(
            "source tree is dirty; use --allow-dirty only for test evidence"
        )
    epoch = int(_git(repo, "show", "-s", "--format=%ct", "HEAD"))
    return observed, clean, datetime.fromtimestamp(epoch, timezone.utc)


def _default_application_version() -> str:
    from sofia.core.package_metadata import application_version
    return application_version()


def _wheel_scope(
    path: Path, kind: str, application_version: str,
) -> dict[str, object]:
    path = Path(path)
    distribution = f"sofia-{kind}"
    try:
        report = inspect_wheel(path, distribution)
    except (ComponentArtifactError, OSError, ValueError) as error:
        raise ReleaseAssemblyError(f"{kind} wheel rejected: {error}") from error
    if report.version != application_version:
        raise ReleaseAssemblyError(
            f"{kind} wheel version {report.version!r} does not match "
            f"application version {application_version!r}"
        )
    for name in report.files:
        folded = name.casefold()
        if any(marker in folded for marker in _CORE_MARKERS):
            raise ReleaseAssemblyError(f"{kind} wheel contains Core payload")
        if any(folded.endswith(suffix) for suffix in _PII_WHEEL_SUFFIXES):
            raise ReleaseAssemblyError(f"{kind} wheel contains a personal state file")
    return {
        "distribution": report.distribution,
        "version": report.version,
        "sha256": report.sha256,
        "requires_dist": list(report.requires_dist),
        "file_count": len(report.files),
    }


def _write_asset(assets: Path, name: str, data: bytes) -> ArtifactReference:
    validate_artifact_path(name)
    if "/" in name or "\\" in name:
        raise ReleaseAssemblyError("asset names must be plain filenames")
    folded = name.casefold()
    if any(marker in folded for marker in _CORE_MARKERS + _ASSET_PII_MARKERS):
        raise ReleaseAssemblyError(f"asset name is not Platform-baseline safe: {name}")
    destination = assets / name
    if destination.exists():
        raise ReleaseAssemblyError(f"duplicate release asset name: {name}")
    destination.write_bytes(data)
    return ArtifactReference(name, _sha256_bytes(data), len(data))


def _copy_asset(assets: Path, source: Path) -> ArtifactReference:
    source = Path(source)
    return _write_asset(assets, source.name, _bounded_read(source))


def _copy_streaming_asset(
    assets: Path, source: Path, name: str,
) -> ArtifactReference:
    source = Path(source)
    validate_artifact_path(name)
    if source.is_symlink() or not source.is_file():
        raise ReleaseAssemblyError(f"release input is not a regular file: {source}")
    if not 1 <= source.stat().st_size <= 512 * 1024**2:
        raise ReleaseAssemblyError(f"release input is outside bounded size: {source}")
    destination = assets / name
    if destination.exists():
        raise ReleaseAssemblyError(f"duplicate release asset name: {name}")
    shutil.copyfile(source, destination)
    return ArtifactReference(
        name, _sha256_file(destination), destination.stat().st_size,
    )


def _runtime_asset(
    assets: Path, *, target: PlatformReleaseTarget, python_version: str,
    python_prefix: Path | None, runtime_archive: Path | None,
) -> tuple[ArtifactReference, dict[str, object]]:
    if bool(python_prefix) == bool(runtime_archive):
        raise ReleaseAssemblyError(
            "exactly one of python_prefix or runtime_archive is required per target"
        )
    destination = assets / "python-runtime.zip"
    if runtime_archive is not None:
        reference = _copy_streaming_asset(
            assets, Path(runtime_archive), "python-runtime.zip",
        )
    else:
        prepared = build_python_runtime(
            Path(python_prefix), destination,
            target=target, python_version=python_version,
        )
        reference = prepared.reference
    manifest = verify_python_runtime(
        destination, expected=reference, target=target,
        python_version=python_version,
    )
    return reference, {
        "file_count": len(manifest.files),
        "manifest_sha256": _sha256_bytes(manifest.canonical_bytes),
        "executable": manifest.executable,
    }


def _discover_native(
    repo: Path, target: PlatformReleaseTarget, kind: str,
) -> Path:
    release_root = Path(repo) / "target" / "release"
    for name in _NATIVE_NAMES[target][kind]:
        candidate = release_root / name
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    expected = " or ".join(_NATIVE_NAMES[target][kind])
    raise ReleaseAssemblyError(
        f"cannot locate {kind} binary for {target.value}; expected {expected} "
        f"under {release_root} or pass --{kind}-binary"
    )


def _native_asset(
    assets: Path, source: Path, *, target: PlatformReleaseTarget, kind: str,
) -> ArtifactReference:
    data = _bounded_read(Path(source))
    try:
        verify_native_target(data, target)
    except (TypeError, ValueError) as error:
        raise ReleaseAssemblyError(
            f"{kind} binary does not match {target.value}: {error}"
        ) from error
    return _write_asset(assets, Path(source).name, data)


def _inventory_payload(
    *, source_sha: str, target: PlatformReleaseTarget,
    python_version: str, assets: list[dict[str, object]],
    wheels: list[dict[str, object]], runtime: dict[str, object],
    native: dict[str, object],
) -> bytes:
    return _json({
        "schema": SCHEMA_INVENTORY,
        "source_sha": source_sha,
        "target": target.value,
        "python_version": python_version,
        "test_signing_only": True,
        "production_authorized": False,
        "artifacts": sorted(assets, key=lambda item: str(item["path"])),
        "wheels": sorted(wheels, key=lambda item: str(item["path"])),
        "runtime": runtime,
        "native": native,
    })


def _sbom_payload(
    *, python_version: str, wheels: list[dict[str, object]],
    runtime: dict[str, object], native: dict[str, object],
) -> bytes:
    return _json({
        "schema": SCHEMA_SBOM,
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "sofia-platform",
                "version": "test-release",
            }
        },
        "python_version": python_version,
        "components": sorted(wheels, key=lambda item: str(item["path"])),
        "runtime": runtime,
        "native": native,
        "standards_compliance_claimed": False,
        "production_authorized": False,
    })


def _provenance_payload(
    *, source_sha: str, target: PlatformReleaseTarget, source_tree_clean: bool,
    created_at: datetime, release_id: str, revision: int,
    python_version: str, artifact_hashes: dict[str, str],
) -> bytes:
    bundle_digest = _sha256_bytes(_json(sorted(artifact_hashes.items())))
    return _json({
        "schema": SCHEMA_PROVENANCE,
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{
            "name": release_id,
            "digest": {"sha256": bundle_digest},
        }],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "aegis.platform.release-assembly/v1",
                "externalParameters": {
                    "source_sha": source_sha,
                    "target": target.value,
                    "python_version": python_version,
                    "revision": revision,
                    "source_tree_clean": source_tree_clean,
                    "test_signing_only": True,
                    "production_authorized": False,
                },
                "resolvedDependencies": sorted(
                    (
                        {"name": name, "digest": {"sha256": digest}}
                        for name, digest in artifact_hashes.items()
                    ),
                    key=lambda item: item["name"],
                ),
            },
            "runDetails": {
                "builder": {"id": "tools.build_aegis_release"},
                "metadata": {
                    "invocationId": release_id,
                    "startedOn": created_at.astimezone(timezone.utc).isoformat(),
                    "source_tree_clean": source_tree_clean,
                    "test_signing_only": True,
                },
            },
        },
        "production_release_attested": False,
        "production_authorized": False,
    })


def _assert_no_secret_material(root: Path, secret: bytes) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size > 8 * 1024**2:
            continue
        if path.suffix.casefold() in {".whl", ".zip", ".exe", ".dll"}:
            continue
        data = path.read_bytes()
        if secret and secret in data:
            raise ReleaseAssemblyError(
                "private signing key material was written into release output"
            )
        if b"BEGIN PRIVATE KEY" in data or b"BEGIN OPENSSH PRIVATE KEY" in data:
            raise ReleaseAssemblyError(
                "private key marker was written into release output"
            )


def _assemble_target(
    *, target: PlatformReleaseTarget, destination: Path,
    source_sha: str, source_tree_clean: bool, created_at: datetime,
    application_version: str, python_version: str, release_id: str,
    revision: int, sdk_wheel: Path, platform_wheel: Path,
    service_binary: Path, tui_binary: Path,
    python_prefix: Path | None, runtime_archive: Path | None,
    private_key, signer_key_id: str,
) -> dict[str, object]:
    assets = destination / "assets"
    assets.mkdir(parents=True, exist_ok=False)
    record: list[dict[str, object]] = []
    wheels_meta: list[dict[str, object]] = []

    sdk_record = _wheel_scope(sdk_wheel, "sdk", application_version)
    sdk_asset = _copy_asset(assets, Path(sdk_wheel))
    if sdk_asset.sha256 != sdk_record["sha256"]:
        raise ReleaseAssemblyError("SDK wheel changed while it was staged")
    record.append({
        "kind": "sdk", "path": sdk_asset.path,
        "sha256": sdk_asset.sha256, "size_bytes": sdk_asset.size_bytes,
    })
    wheels_meta.append({
        "kind": "sdk", "distribution": sdk_record["distribution"],
        "version": sdk_record["version"], "path": sdk_asset.path,
        "sha256": sdk_asset.sha256,
        "requires_dist": sdk_record["requires_dist"],
        "file_count": sdk_record["file_count"],
    })

    platform_record = _wheel_scope(
        platform_wheel, "platform", application_version,
    )
    platform_asset = _copy_asset(assets, Path(platform_wheel))
    if platform_asset.sha256 != platform_record["sha256"]:
        raise ReleaseAssemblyError("Platform wheel changed while it was staged")
    record.append({
        "kind": "platform", "path": platform_asset.path,
        "sha256": platform_asset.sha256, "size_bytes": platform_asset.size_bytes,
    })
    wheels_meta.append({
        "kind": "platform", "distribution": platform_record["distribution"],
        "version": platform_record["version"], "path": platform_asset.path,
        "sha256": platform_asset.sha256,
        "requires_dist": platform_record["requires_dist"],
        "file_count": platform_record["file_count"],
    })

    service_asset = _native_asset(
        assets, Path(service_binary), target=target, kind="service",
    )
    record.append({
        "kind": "service", "path": service_asset.path,
        "sha256": service_asset.sha256, "size_bytes": service_asset.size_bytes,
        "target": target.value,
    })
    tui_asset = _native_asset(
        assets, Path(tui_binary), target=target, kind="tui",
    )
    record.append({
        "kind": "dependency", "path": tui_asset.path,
        "sha256": tui_asset.sha256, "size_bytes": tui_asset.size_bytes,
        "target": target.value, "role": "aegis_tui",
    })

    runtime_asset, runtime_meta = _runtime_asset(
        assets, target=target, python_version=python_version,
        python_prefix=python_prefix, runtime_archive=runtime_archive,
    )
    record.append({
        "kind": "python-runtime", "path": runtime_asset.path,
        "sha256": runtime_asset.sha256, "size_bytes": runtime_asset.size_bytes,
        "target": target.value,
    })
    runtime_meta = dict(runtime_meta, path=runtime_asset.path, sha256=runtime_asset.sha256)
    native_meta = {
        "service": {"path": service_asset.path, "sha256": service_asset.sha256},
        "tui": {"path": tui_asset.path, "sha256": tui_asset.sha256},
    }

    inventory = _inventory_payload(
        source_sha=source_sha, target=target, python_version=python_version,
        assets=record, wheels=wheels_meta, runtime=runtime_meta,
        native=native_meta,
    )
    inventory_asset = _write_asset(assets, "dependency-inventory.json", inventory)
    record.append({
        "kind": "dependency-lock", "path": inventory_asset.path,
        "sha256": inventory_asset.sha256, "size_bytes": inventory_asset.size_bytes,
    })

    sbom = _sbom_payload(
        python_version=python_version, wheels=wheels_meta,
        runtime=runtime_meta, native=native_meta,
    )
    sbom_asset = _write_asset(assets, "sbom.json", sbom)
    record.append({
        "kind": "sbom", "path": sbom_asset.path,
        "sha256": sbom_asset.sha256, "size_bytes": sbom_asset.size_bytes,
    })

    artifact_hashes = {str(item["path"]): str(item["sha256"]) for item in record}
    provenance = _provenance_payload(
        source_sha=source_sha, target=target,
        source_tree_clean=source_tree_clean, created_at=created_at,
        release_id=release_id, revision=revision,
        python_version=python_version, artifact_hashes=artifact_hashes,
    )
    provenance_asset = _write_asset(assets, "assembly-provenance.json", provenance)
    record.append({
        "kind": "provenance", "path": provenance_asset.path,
        "sha256": provenance_asset.sha256, "size_bytes": provenance_asset.size_bytes,
    })

    kinds = [str(item["kind"]) for item in record]
    if set(kinds) < REQUIRED_KINDS:
        missing = sorted(REQUIRED_KINDS - set(kinds))
        raise ReleaseAssemblyError(
            f"incomplete release inventory for {target.value}: {missing}"
        )
    if len(set(kinds)) != len(kinds):
        raise ReleaseAssemblyError("release inventory contains duplicate kinds")
    if len({str(item["path"]).casefold() for item in record}) != len(record):
        raise ReleaseAssemblyError("release inventory contains duplicate paths")

    manifest = PlatformReleaseManifest(
        release_id=release_id,
        version=application_version,
        revision=revision,
        source_sha=source_sha,
        target=target,
        sdk_protocol=SDK_PROTOCOL_VERSION,
        python_version=python_version,
        assets=tuple(
            PlatformReleaseAsset(str(item["kind"]), ArtifactReference(
                str(item["path"]), str(item["sha256"]), int(item["size_bytes"]),
            ))
            for item in record
        ),
    )
    if manifest.source_sha != source_sha:
        raise ReleaseAssemblyError("manifest/source SHA mismatch")
    manifest_bytes = manifest.canonical_bytes
    signature = private_key.sign(manifest.digest.encode("ascii"))
    signature_b64 = b64encode(signature).decode("ascii")
    envelope = _json({
        "signer_key_id": signer_key_id,
        "signature_b64": signature_b64,
    })

    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    verifier = PlatformReleaseVerifier({signer_key_id: public_key})
    verified = verifier.verify(
        manifest.to_payload(),
        signature_b64=signature_b64,
        signer_key_id=signer_key_id,
        assets_root=assets,
        expected_source_sha=source_sha,
        expected_target=target,
        minimum_revision=revision,
    )
    if verified.digest != manifest.digest:
        raise ReleaseAssemblyError("self-verification changed the release digest")

    manifest_path = destination / "release-manifest.json"
    signature_path = destination / "release-signature.json"
    manifest_path.write_bytes(manifest_bytes)
    signature_path.write_bytes(envelope)

    asset_list = sorted(record, key=lambda item: str(item["path"]))
    digests = _json({
        "schema": SCHEMA_DIGESTS,
        "source_sha": source_sha,
        "target": target.value,
        "release_id": release_id,
        "revision": revision,
        "manifest_digest": manifest.digest,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "signature_sha256": _sha256_bytes(signature),
        "signer_key_id": signer_key_id,
        "assets": asset_list,
        "production_signing_claim": False,
        "production_authorized": False,
    })
    (destination / "artifact-digests.json").write_bytes(digests)

    model = {
        "schema": SCHEMA_RECEIPT,
        "result": "TEST_SIGNED_RELEASE_ASSEMBLED_NOT_INSTALLED",
        "source_sha": source_sha,
        "source_tree_clean": source_tree_clean,
        "target": target.value,
        "release_id": release_id,
        "revision": revision,
        "application_version": application_version,
        "python_version": python_version,
        "manifest_digest": manifest.digest,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "signature_sha256": _sha256_bytes(signature),
        "signer_key_id": signer_key_id,
        "artifact_count": len(record),
        "assets": asset_list,
        "inventory_complete": True,
        "core_or_pii_present": False,
        "test_signing_only": True,
        "production_signing_claim": False,
        "production_authorized": False,
        "trust_root_embedded": False,
        "installed_host_verified": False,
        "release_accepted": False,
        "acceptance": "NOT_CLAIMED",
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
    }
    if not source_tree_clean:
        model["result"] = "TEST_SIGNED_RELEASE_ASSEMBLED_DIRTY_SOURCE_TEST_ONLY"
    (destination / "build-receipt.json").write_bytes(_json(model))
    return model


def assemble_release(
    *,
    repo: Path,
    source_sha: str,
    targets: list[PlatformReleaseTarget],
    output_dir: Path,
    test_signing_key: Path,
    signer_key_id: str,
    sdk_wheel: Path | None = None,
    platform_wheel: Path | None = None,
    service_binaries: dict[PlatformReleaseTarget, Path] | None = None,
    tui_binaries: dict[PlatformReleaseTarget, Path] | None = None,
    python_prefixes: dict[PlatformReleaseTarget, Path] | None = None,
    runtime_archives: dict[PlatformReleaseTarget, Path] | None = None,
    application_version: str | None = None,
    python_version: str | None = None,
    release_id: str | None = None,
    revision: int = 1,
    allow_dirty: bool = False,
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Assemble one or more signed test-release bundles, refusing incompleteness."""
    if not isinstance(signer_key_id, str) or not 1 <= len(signer_key_id) <= 128:
        raise ReleaseAssemblyError("bounded signer_key_id required")
    if type(revision) is not int or revision < 1:
        raise ReleaseAssemblyError("positive release revision required")
    version = application_version or _default_application_version()
    py_version = python_version or host_platform.python_version()
    if not _PYTHON_VERSION.fullmatch(py_version):
        raise ReleaseAssemblyError("exact Python 3.12.x runtime version required")
    if not targets:
        raise ReleaseAssemblyError("at least one release target required")
    if len(set(targets)) != len(targets):
        raise ReleaseAssemblyError("duplicate release target")
    for target in targets:
        if not isinstance(target, PlatformReleaseTarget):
            raise ReleaseAssemblyError("typed Platform release target required")

    repo = Path(repo).absolute()
    output_dir = Path(output_dir).absolute()
    key_path = Path(test_signing_key).absolute()
    if output_dir.exists():
        raise ReleaseAssemblyError("release output must not already exist")
    if key_path == output_dir or output_dir in key_path.parents:
        raise ReleaseAssemblyError("test signing key must remain outside release output")
    private_key = load_ed25519_private_key(key_path)
    secret_pem = key_path.read_bytes()

    observed_sha, clean, commit_time = resolve_source_state(
        repo, source_sha, allow_dirty=allow_dirty,
    )
    if created_at is None:
        created_at = commit_time
    if not isinstance(created_at, datetime) or created_at.tzinfo is None:
        raise ReleaseAssemblyError("timezone-aware created_at required")
    if not allow_dirty and not clean:
        raise ReleaseAssemblyError("clean source tree required")

    resolved_service: dict[PlatformReleaseTarget, Path] = {}
    resolved_tui: dict[PlatformReleaseTarget, Path] = {}
    for target in targets:
        resolved_service[target] = (
            Path(service_binaries[target])
            if service_binaries and target in service_binaries
            else _discover_native(repo, target, "service")
        )
        resolved_tui[target] = (
            Path(tui_binaries[target])
            if tui_binaries and target in tui_binaries
            else _discover_native(repo, target, "tui")
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    wheel_temp = Path(tempfile.mkdtemp(prefix=".wheels-", dir=output_dir))
    try:
        if sdk_wheel is None:
            sdk_wheel = build_component("sdk", wheel_temp, repo=repo, version=version)
        if platform_wheel is None:
            platform_wheel = build_component(
                "platform", wheel_temp, repo=repo, version=version,
            )
        # Validate before target assembly so bad wheels never create partial output.
        _wheel_scope(Path(sdk_wheel), "sdk", version)
        _wheel_scope(Path(platform_wheel), "platform", version)

        results = []
        for target in targets:
            final = output_dir / target.value
            staging = Path(tempfile.mkdtemp(prefix=f".{target.value}-", dir=output_dir))
            try:
                prefixes = python_prefixes or {}
                archives = runtime_archives or {}
                release = release_id or (
                    f"aegis-platform-{version}-{observed_sha[:12]}-{target.value}"
                )
                if not _RELEASE_ID.fullmatch(release):
                    raise ReleaseAssemblyError("bounded release_id required")
                model = _assemble_target(
                    target=target,
                    destination=staging,
                    source_sha=observed_sha,
                    source_tree_clean=clean,
                    created_at=created_at,
                    application_version=version,
                    python_version=py_version,
                    release_id=release,
                    revision=revision,
                    sdk_wheel=Path(sdk_wheel),
                    platform_wheel=Path(platform_wheel),
                    service_binary=resolved_service[target],
                    tui_binary=resolved_tui[target],
                    python_prefix=prefixes.get(target),
                    runtime_archive=archives.get(target),
                    private_key=private_key,
                    signer_key_id=signer_key_id,
                )
                staging.replace(final)
                results.append(model)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
    finally:
        shutil.rmtree(wheel_temp, ignore_errors=True)

    _assert_no_secret_material(output_dir, secret_pem)
    return {
        "schema": "aegis.platform.release-assembly-set.v1",
        "source_sha": observed_sha,
        "source_tree_clean": clean,
        "test_signing_only": True,
        "production_signing_claim": False,
        "production_authorized": False,
        "installed_host_verified": False,
        "release_accepted": False,
        "targets": [model["target"] for model in results],
        "releases": results,
    }


def _parse_target(value: str) -> list[PlatformReleaseTarget]:
    if value == "all":
        return [
            PlatformReleaseTarget.WINDOWS_X86_64,
            PlatformReleaseTarget.DEBIAN12_X86_64,
        ]
    return [PlatformReleaseTarget(value)]


def _parse_keyed_paths(
    values: list[str], targets: list[PlatformReleaseTarget],
) -> dict[PlatformReleaseTarget, Path]:
    parsed: dict[PlatformReleaseTarget, Path] = {}
    for value in values:
        target_text, separator, path_text = value.partition("=")
        if separator:
            try:
                target = PlatformReleaseTarget(target_text)
            except ValueError as error:
                raise ReleaseAssemblyError(
                    f"unknown target in {value!r}"
                ) from error
        elif len(targets) == 1:
            target = targets[0]
            path_text = target_text
        else:
            raise ReleaseAssemblyError(
                "TARGET=PATH form required when assembling multiple targets"
            )
        if target in parsed:
            raise ReleaseAssemblyError(f"duplicate input for {target.value}")
        parsed[target] = Path(path_text)
    return parsed


def _derive_targets(args) -> list[PlatformReleaseTarget]:
    targets: list[PlatformReleaseTarget] = []
    for value in args.target:
        for target in _parse_target(value):
            if target not in targets:
                targets.append(target)
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--target", action="append", default=[],
        choices=[target.value for target in PlatformReleaseTarget] + ["all"],
        help="release target; repeatable; default all",
    )
    parser.add_argument("--test-signing-key", type=Path, required=True)
    parser.add_argument("--signer-key-id", required=True)
    parser.add_argument("--sdk-wheel", type=Path)
    parser.add_argument("--platform-wheel", type=Path)
    parser.add_argument(
        "--service-binary", action="append", default=[],
        metavar="[TARGET=]PATH",
    )
    parser.add_argument(
        "--tui-binary", action="append", default=[], metavar="[TARGET=]PATH",
    )
    parser.add_argument(
        "--python-prefix", action="append", default=[],
        metavar="[TARGET=]PATH",
    )
    parser.add_argument(
        "--runtime-archive", action="append", default=[],
        metavar="[TARGET=]PATH",
    )
    parser.add_argument("--application-version")
    parser.add_argument("--python-version")
    parser.add_argument("--release-id")
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--created-at")
    parser.add_argument(
        "--allow-dirty", action="store_true",
        help="test-only mode; records a dirty source tree and refuses production claims",
    )
    args = parser.parse_args(argv)

    try:
        targets = _derive_targets(args) or [
            PlatformReleaseTarget.WINDOWS_X86_64,
            PlatformReleaseTarget.DEBIAN12_X86_64,
        ]
        service = _parse_keyed_paths(args.service_binary, targets)
        tui = _parse_keyed_paths(args.tui_binary, targets)
        prefixes = _parse_keyed_paths(args.python_prefix, targets)
        archives = _parse_keyed_paths(args.runtime_archive, targets)
        created_at = None
        if args.created_at:
            created_at = datetime.fromisoformat(args.created_at)
        result = assemble_release(
            repo=args.repo,
            source_sha=args.source_sha,
            targets=targets,
            output_dir=args.output,
            test_signing_key=args.test_signing_key,
            signer_key_id=args.signer_key_id,
            sdk_wheel=args.sdk_wheel,
            platform_wheel=args.platform_wheel,
            service_binaries=service,
            tui_binaries=tui,
            python_prefixes=prefixes,
            runtime_archives=archives,
            application_version=args.application_version,
            python_version=args.python_version,
            release_id=args.release_id,
            revision=args.revision,
            allow_dirty=args.allow_dirty,
            created_at=created_at,
        )
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (ReleaseAssemblyError, OSError, ValueError, TypeError) as error:
        print(
            json.dumps({
                "schema": SCHEMA_RECEIPT,
                "result": "RELEASE_ASSEMBLY_REFUSED",
                "reason": str(error),
                "test_signing_only": True,
                "production_authorized": False,
                "release_accepted": False,
            }, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
