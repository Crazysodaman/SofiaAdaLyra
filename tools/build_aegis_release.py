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
from collections import Counter
from datetime import datetime, timezone
from email.parser import BytesParser
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform as host_platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT / "src"))
    sys.path.insert(0, str(_ROOT))

from cryptography.exceptions import UnsupportedAlgorithm  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PublicKey,
)

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
SCHEMA_INSTALLER_PLAN = "aegis.installer.install-plan.v1"
SCHEMA_INSTALLER_TRUST = "aegis.installer.trust.v1"
SCHEMA_INSTALLER_PAYLOAD = "aegis.installer.payload-verification.v1"

REQUIRED_KINDS = frozenset({
    "sdk", "platform", "service", "python-runtime",
    "dependency-lock", "sbom", "provenance",
})
MANIFEST_KINDS = REQUIRED_KINDS | frozenset({"dependency"})

INSTALLER_DIR_NAME = "installer"
INSTALLER_ENTRYPOINTS = {
    PlatformReleaseTarget.WINDOWS_X86_64: ("Install-Aegis.ps1",),
    PlatformReleaseTarget.DEBIAN12_X86_64: ("install-aegis.sh",),
}
INSTALLER_SETUP_EXE = "Aegis-Setup.exe"
_INSTALLER_SUFFIXES = frozenset({".ps1", ".sh", ".bat", ".cmd"})
_INSTALLER_RESERVED = frozenset({
    "trusted-publisher.pem", "trust.json", "install-plan.json",
})
RUNTIME_DEPENDENCIES = {
    PlatformReleaseTarget.WINDOWS_X86_64: (
        "cryptography", "cffi", "pycparser", "pywin32", "tzdata",
    ),
    PlatformReleaseTarget.DEBIAN12_X86_64: (
        "cryptography", "cffi", "pycparser", "tzdata",
    ),
}
_RUNTIME_PREFIX = {
    PlatformReleaseTarget.WINDOWS_X86_64: "runtime/python/python.exe",
    PlatformReleaseTarget.DEBIAN12_X86_64: "runtime/python/bin/python3.12",
}
_SERVICE_DEFAULTS = {
    PlatformReleaseTarget.WINDOWS_X86_64: {
        "service_manager": "scm",
        "service_name": "AegisPlatform",
        "service_display_name": "Aegis Platform",
        "install_root": "%PROGRAMFILES%\\Aegis",
        "state_home": "%PROGRAMDATA%\\Aegis",
    },
    PlatformReleaseTarget.DEBIAN12_X86_64: {
        "service_manager": "systemd",
        "service_name": "aegis-platform",
        "service_unit": "aegis-platform.service",
        "service_user": "aegis",
        "service_group": "aegis",
        "install_root": "/opt/aegis",
        "state_home": "/var/lib/aegis",
        "config_home": "/etc/aegis",
    },
}

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


def _normalise_distribution(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _copy_streaming_file(destination: Path, source: Path) -> ArtifactReference:
    """Copy one bounded regular file while hashing the exact published bytes."""
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ReleaseAssemblyError(f"release input is not a regular file: {source}")
    size = source.stat().st_size
    if not 1 <= size <= 512 * 1024**2:
        raise ReleaseAssemblyError(f"release input is outside bounded size: {source}")
    if destination.exists() or destination.is_symlink():
        raise ReleaseAssemblyError(f"duplicate release file: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return ArtifactReference(
        destination.name, _sha256_file(destination), destination.stat().st_size,
    )


def _write_named_file(destination: Path, data: bytes) -> ArtifactReference:
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ReleaseAssemblyError(f"duplicate release file: {destination.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return ArtifactReference(destination.name, _sha256_bytes(data), len(data))


def _public_key_pem(path: Path) -> tuple[bytes, str]:
    """Read an Ed25519 *public* key, refusing private or malformed material."""
    path = Path(path).absolute()
    data = _bounded_read(path, 16_384)
    if (b"PRIVATE KEY" in data
            or b"BEGIN OPENSSH PRIVATE KEY" in data):
        raise ReleaseAssemblyError(
            "installer trust anchor must be a public key, never a private key"
        )
    try:
        key = serialization.load_pem_public_key(data)
    except (TypeError, ValueError, UnsupportedAlgorithm) as error:
        raise ReleaseAssemblyError(
            "installer trust anchor must be a valid PEM public key"
        ) from error
    if not isinstance(key, Ed25519PublicKey):
        raise ReleaseAssemblyError("installer trust anchor must be Ed25519")
    return data, _sha256_bytes(data)


def _resolve_installer_dir(
    repo: Path, installer_dir: Path | None,
) -> Path | None:
    if installer_dir is not None:
        candidate = Path(installer_dir).absolute()
        if candidate.is_symlink() or not candidate.is_dir():
            raise ReleaseAssemblyError("installer payload directory is unavailable")
        return candidate
    candidate = Path(repo) / "packaging" / "installers"
    if candidate.is_dir() and not candidate.is_symlink():
        return candidate
    return None


def _resolve_wheelhouse(
    repo: Path, dependency_wheelhouse: Path | None,
) -> Path | None:
    if dependency_wheelhouse is not None:
        candidate = Path(dependency_wheelhouse).absolute()
        if candidate.is_symlink() or not candidate.is_dir():
            raise ReleaseAssemblyError("offline dependency wheelhouse is unavailable")
        return candidate
    for candidate in (
        Path(repo) / "packaging" / "wheelhouse",
        Path(repo) / "wheelhouse",
        Path(repo) / "packaging" / "installers" / "wheelhouse",
    ):
        if candidate.is_dir() and not candidate.is_symlink():
            return candidate
    return None


def _installer_payload_files(
    installer_dir: Path, targets: list[PlatformReleaseTarget],
) -> list[Path]:
    installer_dir = Path(installer_dir)
    names = {path.name for path in installer_dir.iterdir() if path.is_file()}
    for target in targets:
        for entrypoint in INSTALLER_ENTRYPOINTS[target]:
            if entrypoint not in names:
                raise ReleaseAssemblyError(
                    f"installer payload for {target.value} requires {entrypoint}"
                )
    selected: list[Path] = []
    seen: set[str] = set()
    for path in sorted(installer_dir.iterdir(), key=lambda item: item.name):
        if path.name in _INSTALLER_RESERVED:
            raise ReleaseAssemblyError(
                f"installer payload name is reserved for generated trust data: {path.name}"
            )
        if not (path.name == INSTALLER_SETUP_EXE
                or path.suffix.casefold() in _INSTALLER_SUFFIXES):
            continue
        if path.is_symlink() or not path.is_file():
            raise ReleaseAssemblyError(
                f"installer payload is not a regular file: {path.name}"
            )
        folded = path.name.casefold()
        if folded in seen:
            raise ReleaseAssemblyError("installer payload has ambiguous duplicate names")
        seen.add(folded)
        selected.append(path)
    return selected


def _installer_role(name: str) -> str:
    if name in {name for names in INSTALLER_ENTRYPOINTS.values() for name in names} \
            or name == INSTALLER_SETUP_EXE:
        return "installer-entrypoint"
    return "installer-helper"


def _wheel_identity(path: Path, data: bytes) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            metadata = [
                item for item in archive.infolist()
                if item.filename.endswith(".dist-info/METADATA")
            ]
            if len(metadata) != 1 or metadata[0].file_size > 262_144:
                raise ReleaseAssemblyError(
                    f"dependency wheel metadata is missing or ambiguous: {path.name}"
                )
            parsed = BytesParser().parsebytes(archive.read(metadata[0]))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError) as error:
        raise ReleaseAssemblyError(
            f"dependency wheel is not a valid archive: {path.name}"
        ) from error
    names = parsed.get_all("Name", [])
    versions = parsed.get_all("Version", [])
    if len(names) != 1 or len(versions) != 1:
        raise ReleaseAssemblyError(
            f"dependency wheel identity is ambiguous: {path.name}"
        )
    return names[0], versions[0]


def _wheel_platform_allows(name: str, target: PlatformReleaseTarget) -> bool:
    stem = name[:-4] if name.casefold().endswith(".whl") else name
    parts = stem.split("-")
    if len(parts) < 5:
        return False
    platform_tags = parts[-1].split(".")
    for tag in platform_tags:
        folded = tag.casefold()
        if folded == "any":
            return True
        if (target is PlatformReleaseTarget.WINDOWS_X86_64
                and folded.startswith("win") and "amd64" in folded):
            return True
        if (target is PlatformReleaseTarget.DEBIAN12_X86_64
                and ("linux" in folded or "manylinux" in folded)
                and ("x86_64" in folded or "amd64" in folded)):
            return True
    return False


def _select_dependency_wheels(
    wheelhouse: Path, target: PlatformReleaseTarget,
) -> list[dict[str, object]]:
    wheelhouse = Path(wheelhouse)
    required = RUNTIME_DEPENDENCIES[target]
    wanted = {_normalise_distribution(name) for name in required}
    candidates: dict[str, list[dict[str, object]]] = {
        name: [] for name in wanted
    }
    for path in sorted(wheelhouse.iterdir(), key=lambda item: item.name):
        if path.suffix.casefold() != ".whl":
            continue
        if path.is_symlink() or not path.is_file():
            raise ReleaseAssemblyError(
                f"dependency wheel is not a regular file: {path.name}"
            )
        data = _bounded_read(path, 64 * 1024**2)
        distribution, version = _wheel_identity(path, data)
        normalized = _normalise_distribution(distribution)
        if normalized not in wanted:
            continue
        if not _wheel_platform_allows(path.name, target):
            continue
        try:
            report = inspect_wheel(path, distribution, payload=data)
        except (ComponentArtifactError, OSError, ValueError) as error:
            raise ReleaseAssemblyError(
                f"dependency wheel rejected: {path.name}: {error}"
            ) from error
        candidates[normalized].append({
            "path": path,
            "data": data,
            "distribution": report.distribution,
            "version": report.version,
            "requires_dist": list(report.requires_dist),
        })
    selected: list[dict[str, object]] = []
    for distribution in required:
        matches = candidates[_normalise_distribution(distribution)]
        if not matches:
            raise ReleaseAssemblyError(
                "offline dependency closure is unavailable: "
                f"missing {distribution} for {target.value}"
            )
        if len(matches) > 1:
            names = ", ".join(str(item["path"].name) for item in matches)
            raise ReleaseAssemblyError(
                f"offline dependency closure is ambiguous for {distribution}: {names}"
            )
        selected.append(matches[0])
    return selected


def _stage_dependency_wheels(
    assets: Path, wheelhouse: Path, target: PlatformReleaseTarget,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    metadata: list[dict[str, object]] = []
    for item in _select_dependency_wheels(wheelhouse, target):
        source = Path(item["path"])
        data = bytes(item["data"])
        relative = f"wheelhouse/{source.name}"
        validate_artifact_path(relative)
        destination = assets.joinpath(*relative.split("/"))
        reference = _write_named_file(destination, data)
        records.append({
            "kind": "dependency",
            "role": "runtime-dependency",
            "path": relative,
            "sha256": reference.sha256,
            "size_bytes": reference.size_bytes,
            "target": target.value,
        })
        metadata.append({
            "kind": "runtime-dependency",
            "distribution": item["distribution"],
            "version": item["version"],
            "path": relative,
            "sha256": reference.sha256,
            "size_bytes": reference.size_bytes,
            "requires_dist": item["requires_dist"],
        })
    return records, metadata


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
    native: dict[str, object], installer: list[dict[str, object]],
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
        "installer": sorted(installer, key=lambda item: str(item["path"])),
        "installer_payload_included": bool(installer),
    })


def _sbom_payload(
    *, python_version: str, wheels: list[dict[str, object]],
    runtime: dict[str, object], native: dict[str, object],
    installer: list[dict[str, object]],
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
        "installer_payload": sorted(
            installer, key=lambda item: str(item["path"]),
        ),
        "standards_compliance_claimed": False,
        "production_authorized": False,
    })


def _provenance_payload(
    *, source_sha: str, target: PlatformReleaseTarget, source_tree_clean: bool,
    created_at: datetime, release_id: str, revision: int,
    python_version: str, artifact_hashes: dict[str, str],
    installer_payload_included: bool, trust_anchor_sha256: str | None,
    wheelhouse_distributions: list[str],
) -> bytes:
    bundle_digest = _sha256_bytes(_json(sorted(artifact_hashes.items())))
    external = {
        "source_sha": source_sha,
        "target": target.value,
        "python_version": python_version,
        "revision": revision,
        "source_tree_clean": source_tree_clean,
        "test_signing_only": True,
        "production_authorized": False,
        "installer_payload_included": bool(installer_payload_included),
        "wheelhouse_distributions": sorted(wheelhouse_distributions),
    }
    if trust_anchor_sha256 is not None:
        external["trust_anchor_sha256"] = trust_anchor_sha256
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
                "externalParameters": external,
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


def _install_plan_payload(
    *, source_sha: str, target: PlatformReleaseTarget, revision: int,
    release_id: str, application_version: str, python_version: str,
    entrypoints: dict[str, str | None], installer_files: list[dict[str, object]],
    trust_anchor: dict[str, object], wheelhouse: list[dict[str, object]],
    runtime: dict[str, object], service_binary: str, tui_binary: str,
) -> bytes:
    setup_exe = entrypoints.get(INSTALLER_SETUP_EXE)
    operator_apps = {
        "gui": f"installer/{setup_exe}" if setup_exe else None,
        "tui": f"assets/{tui_binary}",
        "start_menu": (
            "Aegis Platform"
            if target is PlatformReleaseTarget.WINDOWS_X86_64 else None
        ),
        "desktop_entry": (
            "aegis-platform.desktop"
            if target is PlatformReleaseTarget.DEBIAN12_X86_64 else None
        ),
        "requested": False,
        "requires_owner_approval": True,
    }
    return _json({
        "schema": SCHEMA_INSTALLER_PLAN,
        "result": "INSTALL_PLAN_ONLY_NOT_AUTHORITY",
        "authority": "PLAN_ONLY_NOT_AUTHORITY",
        "grants_authority": False,
        "executed": False,
        "production_authorized": False,
        "test_signing_only": True,
        "bundle_source_sha": source_sha,
        "target": target.value,
        "revision": revision,
        "release_id": release_id,
        "application_version": application_version,
        "python_version": python_version,
        "installer_entrypoints": {
            name: f"installer/{path}" if path else None
            for name, path in entrypoints.items()
        },
        "installer_check_commands": {
            "windows": "installer/Install-Aegis.ps1 -Check",
            "debian": "installer/install-aegis.sh --check",
        },
        "installer_files": sorted(
            installer_files, key=lambda item: str(item["path"]),
        ),
        "trust_anchor": trust_anchor,
        "runtime": runtime,
        "wheelhouse": {
            "path": "assets/wheelhouse",
            "required_distributions": list(RUNTIME_DEPENDENCIES[target]),
            "wheels": sorted(
                (
                    dict(item, path=f"assets/{item['path']}")
                    for item in wheelhouse
                ),
                key=lambda item: str(item["path"]),
            ),
        },
        "service_defaults": {
            **_SERVICE_DEFAULTS[target],
            "service_binary": f"assets/{service_binary}",
            "runtime_python": _RUNTIME_PREFIX[target],
        },
        "operator_app_defaults": operator_apps,
        "release_signature_separate": True,
        "installer_trust_separate_from_release_signature": True,
    })


def _stage_installer_payload(
    *, destination: Path, installer_dir: Path,
    targets: list[PlatformReleaseTarget], target: PlatformReleaseTarget,
    trusted_public_key: Path, trusted_signer_key_id: str,
    release_signer_key_id: str, source_sha: str, revision: int,
    release_id: str, application_version: str, python_version: str,
    wheelhouse: list[dict[str, object]], runtime: dict[str, object],
    service_binary: str, tui_binary: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    installer_root = Path(destination)
    installer_root.mkdir(parents=True, exist_ok=False)
    files = _installer_payload_files(installer_dir, targets)
    records: list[dict[str, object]] = []
    entries: dict[str, Path] = {}
    for source in files:
        reference = _copy_streaming_file(installer_root / source.name, source)
        entries[source.name] = installer_root / source.name
        records.append({
            "role": _installer_role(source.name),
            "path": f"installer/{source.name}",
            "sha256": reference.sha256,
            "size_bytes": reference.size_bytes,
        })

    public_pem, public_digest = _public_key_pem(trusted_public_key)
    trust_path = installer_root / "trusted-publisher.pem"
    trust_reference = _write_named_file(trust_path, public_pem)
    records.append({
        "role": "installer-trust-anchor",
        "path": "installer/trusted-publisher.pem",
        "sha256": trust_reference.sha256,
        "size_bytes": trust_reference.size_bytes,
    })
    trust = {
        "schema": SCHEMA_INSTALLER_TRUST,
        "signer_key_id": trusted_signer_key_id,
        "trusted_public_key": "installer/trusted-publisher.pem",
        "public_key_sha256": public_digest,
        "public_key_type": "Ed25519",
        "private_key_included": False,
        "applies_to": "installer-payload-and-install-plan",
        "release_signature_separate": True,
        "release_signer_key_id": release_signer_key_id,
        "test_signing_only": True,
        "production_authorized": False,
    }
    trust_bytes = _json(trust)
    trust_record = _write_named_file(installer_root / "trust.json", trust_bytes)
    records.append({
        "role": "installer-trust-record",
        "path": "installer/trust.json",
        "sha256": trust_record.sha256,
        "size_bytes": trust_record.size_bytes,
    })

    entrypoints: dict[str, str | None] = {
        "Install-Aegis.ps1": "Install-Aegis.ps1"
        if "Install-Aegis.ps1" in entries else None,
        "install-aegis.sh": "install-aegis.sh"
        if "install-aegis.sh" in entries else None,
        INSTALLER_SETUP_EXE: INSTALLER_SETUP_EXE
        if INSTALLER_SETUP_EXE in entries else None,
    }
    trust_anchor = {
        "path": "installer/trusted-publisher.pem",
        "sha256": public_digest,
        "signer_key_id": trusted_signer_key_id,
        "trust_record": "installer/trust.json",
        "release_signature_separate": True,
    }
    plan = _install_plan_payload(
        source_sha=source_sha, target=target, revision=revision,
        release_id=release_id, application_version=application_version,
        python_version=python_version, entrypoints=entrypoints,
        installer_files=records, trust_anchor=trust_anchor,
        wheelhouse=wheelhouse, runtime=runtime,
        service_binary=service_binary, tui_binary=tui_binary,
    )
    plan_record = _write_named_file(installer_root / "install-plan.json", plan)
    records.append({
        "role": "installer-plan",
        "path": "installer/install-plan.json",
        "sha256": plan_record.sha256,
        "size_bytes": plan_record.size_bytes,
    })
    meta = {
        "entrypoints": {
            name: f"installer/{value}" if value else None
            for name, value in entrypoints.items()
        },
        "trust_anchor": trust_anchor,
        "plan_path": "installer/install-plan.json",
        "plan_sha256": plan_record.sha256,
        "plan_size_bytes": plan_record.size_bytes,
        "payload_count": len(records),
    }
    return records, meta


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
        if any(
            marker in data
            for marker in (
                b"-----BEGIN PRIVATE KEY-----\n",
                b"-----BEGIN PRIVATE KEY-----\r\n",
                b"-----BEGIN OPENSSH PRIVATE KEY-----\n",
                b"-----BEGIN OPENSSH PRIVATE KEY-----\r\n",
            )
        ):
            raise ReleaseAssemblyError(
                "a PEM private key block was written into release output"
            )


def _extract_runtime_tree(runtime_zip: Path, destination: Path) -> None:
    """Materialize the already-verified runtime archive for one-step launch.

    The ZIP itself remains the signed release asset. The extracted tree is an
    installer convenience copy under the bundle, never a new release authority.
    """
    destination = Path(destination).absolute()
    if destination.exists():
        raise ReleaseAssemblyError("runtime extraction destination already exists")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(runtime_zip) as archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            directory_entry = info.is_dir() and name.endswith("/")
            if directory_entry:
                name = name[:-1]
            parts = name.split("/")
            if (
                name.startswith("/")
                or not name
                or any(part in {"", ".", ".."} for part in parts)
                or (parts[0] != "python" and name != "runtime-manifest.json")
            ):
                raise ReleaseAssemblyError("runtime archive member path is unsafe")
            target = destination.joinpath(*parts)
            if directory_entry:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, length=65536)


def _install_runtime_wheels(
    runtime_prefix: Path, wheels: list[Path], *, target: PlatformReleaseTarget,
) -> None:
    """Unpack the exact signed wheels into the extracted runtime site-packages."""
    if target is PlatformReleaseTarget.WINDOWS_X86_64:
        site_packages = runtime_prefix / "Lib" / "site-packages"
    else:
        site_packages = runtime_prefix / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as archive:
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if info.is_dir() or name.endswith("/"):
                    continue
                parts = name.split("/")
                if name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
                    raise ReleaseAssemblyError("runtime wheel member path is unsafe")
                # Wheel .data/purelib and .data/platlib map into site-packages.
                if parts[0].endswith(".data") and len(parts) >= 3 and parts[1] in {
                    "purelib", "platlib",
                }:
                    parts = parts[2:]
                elif parts[0].endswith(".data"):
                    continue
                target_path = site_packages.joinpath(*parts)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target_path.open("wb") as sink:
                    shutil.copyfileobj(source, sink, length=65536)


def _assemble_target(
    *, target: PlatformReleaseTarget, destination: Path,
    source_sha: str, source_tree_clean: bool, created_at: datetime,
    application_version: str, python_version: str, release_id: str,
    revision: int, sdk_wheel: Path, platform_wheel: Path,
    service_binary: Path, tui_binary: Path,
    python_prefix: Path | None, runtime_archive: Path | None,
    private_key, signer_key_id: str,
    installer_dir: Path | None, trusted_public_key: Path | None,
    trusted_signer_key_id: str | None, dependency_wheelhouse: Path | None,
) -> dict[str, object]:
    # Installable bundle layout: independent installer trust lives at
    # <root>/installer, signed release media lives at <root>/release.
    # Guided discovery deliberately refuses a trust anchor inside release media.
    release_root = destination / "release"
    assets = release_root / "assets"
    assets.mkdir(parents=True, exist_ok=False)
    record: list[dict[str, object]] = []
    wheels_meta: list[dict[str, object]] = []
    installer_record: list[dict[str, object]] = []
    installer_meta: dict[str, object] = {}

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

    wheelhouse_record: list[dict[str, object]] = []
    if dependency_wheelhouse is not None:
        wheelhouse_record, wheelhouse_meta = _stage_dependency_wheels(
            assets, dependency_wheelhouse, target,
        )
        record.extend(wheelhouse_record)
        wheels_meta.extend(wheelhouse_meta)

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

    runtime_plan = {
        "archive_path": f"assets/{runtime_asset.path}",
        "archive_sha256": runtime_asset.sha256,
        "archive_size_bytes": runtime_asset.size_bytes,
        "extracted_prefix": "runtime/python",
        "executable": _RUNTIME_PREFIX[target],
        "python_version": python_version,
        "target": target.value,
    }
    if installer_dir is not None:
        runtime_prefix = release_root / "runtime" / "python"
        _extract_runtime_tree(assets / runtime_asset.path, release_root / "runtime")
        _install_runtime_wheels(
            runtime_prefix,
            [
                assets / sdk_asset.path,
                assets / platform_asset.path,
                *[
                    assets / str(item["path"])
                    for item in wheelhouse_record
                ],
            ],
            target=target,
        )
        if trusted_public_key is None or not trusted_signer_key_id:
            raise ReleaseAssemblyError(
                "installer payload requires an independent trusted public key "
                "and signer key ID"
            )
        if dependency_wheelhouse is None:
            raise ReleaseAssemblyError(
                "installer payload requires an offline dependency wheelhouse"
            )
        trust_pem, _trust_digest = _public_key_pem(trusted_public_key)
        release_public = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        trust_public = serialization.load_pem_public_key(trust_pem).public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )
        if trust_public != release_public or trusted_signer_key_id != signer_key_id:
            raise ReleaseAssemblyError(
                "installer publisher trust must match the release signer key/id"
            )
        installer_record, installer_meta = _stage_installer_payload(
            destination=destination / INSTALLER_DIR_NAME,
            installer_dir=installer_dir,
            targets=[target],
            target=target,
            trusted_public_key=trusted_public_key,
            trusted_signer_key_id=trusted_signer_key_id,
            release_signer_key_id=signer_key_id,
            source_sha=source_sha,
            revision=revision,
            release_id=release_id,
            application_version=application_version,
            python_version=python_version,
            wheelhouse=[
                item for item in wheels_meta
                if item.get("kind") == "runtime-dependency"
            ],
            runtime=runtime_plan,
            service_binary=service_asset.path,
            tui_binary=tui_asset.path,
        )

    inventory = _inventory_payload(
        source_sha=source_sha, target=target, python_version=python_version,
        assets=record, wheels=wheels_meta, runtime=runtime_meta,
        native=native_meta, installer=installer_record,
    )
    inventory_asset = _write_asset(assets, "dependency-inventory.json", inventory)
    record.append({
        "kind": "dependency-lock", "path": inventory_asset.path,
        "sha256": inventory_asset.sha256, "size_bytes": inventory_asset.size_bytes,
    })

    sbom = _sbom_payload(
        python_version=python_version, wheels=wheels_meta,
        runtime=runtime_meta, native=native_meta, installer=installer_record,
    )
    sbom_asset = _write_asset(assets, "sbom.json", sbom)
    record.append({
        "kind": "sbom", "path": sbom_asset.path,
        "sha256": sbom_asset.sha256, "size_bytes": sbom_asset.size_bytes,
    })

    artifact_hashes = {str(item["path"]): str(item["sha256"]) for item in record}
    artifact_hashes.update({
        str(item["path"]): str(item["sha256"]) for item in installer_record
    })
    trust_anchor_sha256 = None
    if installer_meta:
        trust_anchor_sha256 = str(
            installer_meta["trust_anchor"]["sha256"]  # type: ignore[index]
        )
    provenance = _provenance_payload(
        source_sha=source_sha, target=target,
        source_tree_clean=source_tree_clean, created_at=created_at,
        release_id=release_id, revision=revision,
        python_version=python_version, artifact_hashes=artifact_hashes,
        installer_payload_included=bool(installer_record),
        trust_anchor_sha256=trust_anchor_sha256,
        wheelhouse_distributions=[
            str(item["distribution"]) for item in wheels_meta
            if item.get("kind") == "runtime-dependency"
        ],
    )
    provenance_asset = _write_asset(assets, "assembly-provenance.json", provenance)
    record.append({
        "kind": "provenance", "path": provenance_asset.path,
        "sha256": provenance_asset.sha256, "size_bytes": provenance_asset.size_bytes,
    })

    kinds = [str(item["kind"]) for item in record]
    counts = Counter(kinds)
    missing = sorted(REQUIRED_KINDS - set(kinds))
    if missing:
        raise ReleaseAssemblyError(
            f"incomplete release inventory for {target.value}: {missing}"
        )
    if any(counts[kind] != 1 for kind in REQUIRED_KINDS):
        raise ReleaseAssemblyError(
            "every required release artifact must occur exactly once"
        )
    if set(kinds) - MANIFEST_KINDS:
        raise ReleaseAssemblyError("release inventory contains an unsupported kind")
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

    manifest_path = release_root / "release-manifest.json"
    signature_path = release_root / "release-signature.json"
    manifest_path.write_bytes(manifest_bytes)
    signature_path.write_bytes(envelope)

    asset_list = sorted(record, key=lambda item: str(item["path"]))
    installer_list = sorted(
        installer_record, key=lambda item: str(item["path"]),
    )
    wheelhouse_list = sorted(
        (
            item for item in wheels_meta
            if item.get("kind") == "runtime-dependency"
        ),
        key=lambda item: str(item["path"]),
    )
    trust_meta = installer_meta.get("trust_anchor") if installer_meta else None
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
        "installer": installer_list,
        "installer_payload_included": bool(installer_list),
        "trust_anchor": trust_meta,
        "wheelhouse": wheelhouse_list,
        "production_signing_claim": False,
        "production_authorized": False,
    })
    (release_root / "artifact-digests.json").write_bytes(digests)

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
        "installer_payload_included": bool(installer_list),
        "installer_payload_count": len(installer_list),
        "installer": installer_list,
        "installer_meta": installer_meta,
        "trust_anchor_sha256": (
            str(trust_meta["sha256"]) if trust_meta else None
        ),
        "trust_anchor_signer_key_id": (
            str(trust_meta["signer_key_id"]) if trust_meta else None
        ),
        "installer_trust_is_release_trust": False,
        "wheelhouse": wheelhouse_list,
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
    (release_root / "build-receipt.json").write_bytes(_json(model))
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
    installer_dir: Path | None = None,
    trusted_public_key: Path | None = None,
    trusted_signer_key_id: str | None = None,
    dependency_wheelhouse: Path | None = None,
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

    resolved_installer_dir = _resolve_installer_dir(repo, installer_dir)
    if trusted_public_key is not None:
        trusted_public_key = Path(trusted_public_key).absolute()
        if trusted_public_key == key_path:
            raise ReleaseAssemblyError(
                "installer trust anchor must not be the private signing key"
            )
        if not trusted_signer_key_id:
            trusted_signer_key_id = signer_key_id
        _public_key_pem(trusted_public_key)
    elif trusted_signer_key_id is not None:
        raise ReleaseAssemblyError(
            "trusted signer key ID requires an independent trusted public key"
        )
    if resolved_installer_dir is not None:
        if trusted_public_key is None:
            raise ReleaseAssemblyError(
                "installer payload requires an independent trusted public key"
            )
        if dependency_wheelhouse is None:
            detected = _resolve_wheelhouse(repo, None)
            if detected is None:
                raise ReleaseAssemblyError(
                    "installer payload requires an offline dependency wheelhouse"
                )
            dependency_wheelhouse = detected
    elif trusted_public_key is not None:
        raise ReleaseAssemblyError(
            "trusted public key was supplied without an installer payload"
        )
    if dependency_wheelhouse is not None:
        dependency_wheelhouse = Path(dependency_wheelhouse).absolute()
        if (dependency_wheelhouse.is_symlink()
                or not dependency_wheelhouse.is_dir()):
            raise ReleaseAssemblyError("offline dependency wheelhouse is unavailable")
        if key_path == dependency_wheelhouse or dependency_wheelhouse in key_path.parents:
            raise ReleaseAssemblyError(
                "private signing key must remain outside the dependency wheelhouse"
            )
        if output_dir == dependency_wheelhouse or output_dir in dependency_wheelhouse.parents:
            raise ReleaseAssemblyError(
                "dependency wheelhouse must remain outside release output"
            )

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
                    installer_dir=resolved_installer_dir,
                    trusted_public_key=trusted_public_key,
                    trusted_signer_key_id=(
                        trusted_signer_key_id or signer_key_id
                        if trusted_public_key is not None else None
                    ),
                    dependency_wheelhouse=dependency_wheelhouse,
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


def verify_installer_payload(
    bundle_root: Path | str, *,
    trusted_public_key: Path | str | None = None,
    trusted_key_sha256: str | None = None,
    trusted_signer_key_id: str | None = None,
) -> dict[str, object]:
    """Verify installer/ payload against its signed-plan/trust digest inventory.

    This is deliberately separate from the release signature. Both must pass.
    No owner approval, installation, service change or runtime execution occurs.
    """
    root = Path(bundle_root).absolute()
    if not root.is_dir() or root.is_symlink():
        raise ReleaseAssemblyError("installer bundle root is unavailable")
    release_root = root / "release"
    if not (release_root / "artifact-digests.json").is_file():
        # Backward-compatible flat media remains readable, but installable
        # bundles from this builder use the independent release/ layout.
        release_root = root
    digests = json.loads(
        _bounded_read(release_root / "artifact-digests.json", 2 * 1024**2).decode("utf-8")
    )
    installer = digests.get("installer")
    if not isinstance(installer, list) or not installer:
        raise ReleaseAssemblyError("bundle does not contain an installer payload")
    provenance = json.loads(
        _bounded_read(
            release_root / "assets" / "assembly-provenance.json", 2 * 1024**2,
        ).decode("utf-8")
    )
    resolved = {
        item.get("name"): item.get("digest", {}).get("sha256")
        for item in provenance.get("predicate", {})
        .get("buildDefinition", {})
        .get("resolvedDependencies", [])
        if isinstance(item, dict)
    }
    for entry in installer:
        if type(entry) is not dict:
            raise ReleaseAssemblyError("installer digest inventory is malformed")
        relative = entry.get("path")
        if type(relative) is not str or not relative.startswith("installer/"):
            raise ReleaseAssemblyError("installer digest path escapes installer/")
        validate_artifact_path(relative)
        expected_sha = entry.get("sha256")
        if type(expected_sha) is not str or not _SHA256.fullmatch(expected_sha):
            raise ReleaseAssemblyError("installer digest inventory is malformed")
        file = root.joinpath(*relative.split("/"))
        if file.is_symlink() or not file.is_file():
            raise ReleaseAssemblyError(
                f"installer payload file is missing: {relative}"
            )
        if file.stat().st_size != entry.get("size_bytes"):
            raise ReleaseAssemblyError(
                f"installer payload size differs: {relative}"
            )
        if _sha256_file(file) != expected_sha:
            raise ReleaseAssemblyError(
                f"installer payload digest differs: {relative}"
            )
        if resolved.get(relative) != expected_sha:
            raise ReleaseAssemblyError(
                f"installer payload digest is not bound by signed provenance: {relative}"
            )

    plan_path = root / "installer" / "install-plan.json"
    plan = json.loads(_bounded_read(plan_path, 2 * 1024**2).decode("utf-8"))
    if plan.get("schema") != SCHEMA_INSTALLER_PLAN:
        raise ReleaseAssemblyError("installer plan schema is unsupported")
    if plan.get("grants_authority") is not False:
        raise ReleaseAssemblyError("installer plan must not grant authority")
    if plan.get("bundle_source_sha") != digests.get("source_sha"):
        raise ReleaseAssemblyError("installer plan source SHA differs")
    if plan.get("target") != digests.get("target"):
        raise ReleaseAssemblyError("installer plan target differs")
    if plan.get("revision") != digests.get("revision"):
        raise ReleaseAssemblyError("installer plan revision differs")
    plan_files = plan.get("installer_files")
    if not isinstance(plan_files, list):
        raise ReleaseAssemblyError("installer plan file inventory is malformed")
    expected_files = {
        entry["path"]: entry["sha256"]
        for entry in installer
        if entry.get("path") != "installer/install-plan.json"
    }
    observed_files = {
        item.get("path"): item.get("sha256")
        for item in plan_files if isinstance(item, dict)
    }
    if observed_files != expected_files:
        raise ReleaseAssemblyError(
            "installer plan file inventory differs from the delivery digests"
        )

    trust_path = root / "installer" / "trust.json"
    trust = json.loads(_bounded_read(trust_path, 64 * 1024).decode("utf-8"))
    if trust.get("schema") != SCHEMA_INSTALLER_TRUST:
        raise ReleaseAssemblyError("installer trust record schema is unsupported")
    if trust.get("private_key_included") is not False:
        raise ReleaseAssemblyError("installer trust record must not embed a private key")
    if trust.get("release_signature_separate") is not True:
        raise ReleaseAssemblyError("installer trust must remain separate from release trust")
    pem_path = root / "installer" / "trusted-publisher.pem"
    _pem, pem_digest = _public_key_pem(pem_path)
    if trust.get("public_key_sha256") != pem_digest:
        raise ReleaseAssemblyError("installer trust anchor digest differs")
    anchor = plan.get("trust_anchor")
    if type(anchor) is not dict:
        raise ReleaseAssemblyError("installer plan trust anchor is missing")
    if (anchor.get("sha256") != pem_digest
            or anchor.get("signer_key_id") != trust.get("signer_key_id")):
        raise ReleaseAssemblyError("installer plan trust anchor differs")
    if trusted_key_sha256 is not None:
        if trusted_key_sha256 != pem_digest:
            raise ReleaseAssemblyError(
                "installer trust anchor differs from the independently pinned digest"
            )
    if trusted_signer_key_id is not None:
        if trusted_signer_key_id != trust.get("signer_key_id"):
            raise ReleaseAssemblyError(
                "installer trust anchor signer differs from the pinned signer"
            )
    if trusted_public_key is not None:
        external, external_digest = _public_key_pem(Path(trusted_public_key))
        if external_digest != pem_digest:
            raise ReleaseAssemblyError(
                "installer trust anchor differs from the independently provisioned key"
            )
    else:
        external_digest = None
    return {
        "schema": SCHEMA_INSTALLER_PAYLOAD,
        "result": "INSTALLER_PAYLOAD_VERIFIED",
        "installer_payload_verified": True,
        "trust_anchor_sha256": pem_digest,
        "externally_pinned_key_sha256": external_digest,
        "signer_key_id": trust.get("signer_key_id"),
        "installer_payload_count": len(installer),
        "installer_entrypoints": plan.get("installer_entrypoints", {}),
        "service_defaults": plan.get("service_defaults", {}),
        "operator_app_defaults": plan.get("operator_app_defaults", {}),
        "wheelhouse": plan.get("wheelhouse", {}),
        "grants_authority": False,
        "owner_approved": False,
        "executed": False,
        "installed": False,
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
        "--installer-dir", type=Path,
        help="installer payload directory; defaults to packaging/installers",
    )
    parser.add_argument(
        "--trusted-public-key", type=Path,
        help="independent Ed25519 publisher PEM for installer trust",
    )
    parser.add_argument(
        "--trusted-signer-key-id",
        help="installer trust signer ID; defaults to --signer-key-id",
    )
    parser.add_argument(
        "--dependency-wheelhouse", type=Path,
        help="offline runtime wheelhouse; defaults to a local packaging/wheelhouse",
    )
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
            installer_dir=args.installer_dir,
            trusted_public_key=args.trusted_public_key,
            trusted_signer_key_id=args.trusted_signer_key_id,
            dependency_wheelhouse=args.dependency_wheelhouse,
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

