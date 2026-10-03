"""Release supply-chain construction for PKG-DEV/VERIFY.

This module constructs deterministic evidence from already-resolved inputs.
Dependency resolution itself is intentionally separate: a production release
must supply an exact lock file rather than silently resolve floating
dependencies during a trusted build.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import platform
import re
import zipfile

from sofia.dev.release import ReleaseManifest
from sofia.run.release import directory_sha256


_PIN = re.compile(
    r"^([A-Za-z0-9_.-]+)==([^\\s;]+)(?:\\s+--hash=sha256:([0-9a-f]{64}))?$"
)


def sha256_file(path: Path) -> str:
    if not isinstance(path, Path) or not path.is_file():
        raise FileNotFoundError("release input file does not exist")
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class LockedDependency:
    name: str
    version: str
    sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("locked dependency name/version required")
        if self.sha256 is not None and (
            len(self.sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in self.sha256)
        ):
            raise ValueError("dependency digest must be lowercase SHA-256")


def parse_requirements_lock(path: Path) -> tuple[LockedDependency, ...]:
    """Parse an exact pip-style lock with name==version entries."""
    if not isinstance(path, Path) or not path.is_file():
        raise FileNotFoundError("dependency lock does not exist")
    entries: list[LockedDependency] = []
    seen: set[str] = set()
    for number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _PIN.fullmatch(line)
        if match is None:
            raise ValueError(
                f"dependency lock line {number} is not an exact pin"
            )
        name, version, digest = match.groups()
        key = name.casefold().replace("_", "-")
        if key in seen:
            raise ValueError(f"duplicate dependency lock entry: {name}")
        seen.add(key)
        entries.append(LockedDependency(name, version, digest))
    if not entries:
        raise ValueError("dependency lock must contain at least one exact pin")
    return tuple(sorted(entries, key=lambda item: item.name.casefold()))


def canonical_dependency_lock(path: Path) -> bytes:
    entries = parse_requirements_lock(path)
    return (
        "\n".join(
            (
                f"{item.name}=={item.version}"
                + (
                    ""
                    if item.sha256 is None
                    else f" --hash=sha256:{item.sha256}"
                )
            )
            for item in entries
        )
        + "\n"
    ).encode("utf-8")


def generate_sbom(
    lock_path: Path,
    *,
    application_name: str,
    application_version: str,
) -> bytes:
    entries = parse_requirements_lock(lock_path)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": application_name,
                "version": application_version,
            }
        },
        "components": [
            {
                "type": "library",
                "name": item.name,
                "version": item.version,
                **(
                    {}
                    if item.sha256 is None
                    else {
                        "hashes": [
                            {
                                "alg": "SHA-256",
                                "content": item.sha256,
                            }
                        ]
                    }
                ),
            }
            for item in entries
        ],
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def generate_provenance(
    *,
    git_revision: str,
    artifact_sha256: str,
    dependency_lock_sha256: str,
    sbom_sha256: str,
    source_sha256: str,
    created_at: datetime,
) -> bytes:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("provenance timestamp must be timezone-aware")
    document = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "sofia-release-artifact",
                "digest": {"sha256": artifact_sha256},
            }
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "sofia-ada-lyra/python-wheel/v1",
                "externalParameters": {
                    "git_revision": git_revision,
                    "python": platform.python_version(),
                },
                "resolvedDependencies": [
                    {
                        "uri": "file:requirements.lock",
                        "digest": {"sha256": dependency_lock_sha256},
                    },
                    {
                        "uri": "file:sbom.cdx.json",
                        "digest": {"sha256": sbom_sha256},
                    },
                    {
                        "uri": "source:repository",
                        "digest": {"sha256": source_sha256},
                    },
                ],
            },
            "runDetails": {
                "builder": {"id": "sofia.dev.supply_chain"},
                "metadata": {
                    "invocationId": git_revision,
                    "startedOn": created_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                },
            },
        },
    }
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def verify_wheel_identity(wheel_path: Path) -> None:
    """Reject malformed wheels before manifest construction."""
    if not wheel_path.name.endswith(".whl"):
        raise ValueError("release artifact must be a wheel")
    with zipfile.ZipFile(wheel_path, "r") as archive:
        names = archive.namelist()
        if not any(name.endswith(".dist-info/RECORD") for name in names):
            raise ValueError("wheel is missing dist-info/RECORD")
        if any(
            name.startswith("/") or ".." in Path(name).parts
            for name in names
        ):
            raise ValueError("wheel contains unsafe archive paths")


@dataclass(frozen=True, slots=True)
class SupplyChainArtifacts:
    manifest_path: Path
    sbom_path: Path
    provenance_path: Path
    dependency_lock_path: Path
    artifact_path: Path
    manifest: ReleaseManifest


def construct_release_evidence(
    *,
    release_id: str,
    git_revision: str,
    application_version: str,
    python_version: str,
    dependency_lock_path: Path,
    wheel_path: Path,
    source_dir: Path,
    constitution_sha256: str,
    state_schema_min: int,
    state_schema_max: int,
    fleet_protocol_version: str,
    fleet_agent_version: str,
    configuration_schema_version: int,
    output_dir: Path,
    created_at: datetime,
    parent_release_id: str | None = None,
    parent_manifest_sha256: str | None = None,
    model_id: str | None = None,
    model_sha256: str | None = None,
    asset_sha256: tuple[tuple[str, str], ...] = (),
) -> SupplyChainArtifacts:
    if not isinstance(output_dir, Path):
        raise TypeError("output_dir must be a Path")
    verify_wheel_identity(wheel_path)
    lock_bytes = canonical_dependency_lock(dependency_lock_path)
    lock_digest = sha256(lock_bytes).hexdigest()
    sbom = generate_sbom(
        dependency_lock_path,
        application_name="sofia-ada-lyra",
        application_version=application_version,
    )
    sbom_digest = sha256(sbom).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = output_dir / "artifact"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_out = artifact_dir / wheel_path.name
    artifact_out.write_bytes(wheel_path.read_bytes())
    artifact_digest = directory_sha256(artifact_dir)
    source_digest = directory_sha256(source_dir)
    provenance = generate_provenance(
        git_revision=git_revision,
        artifact_sha256=artifact_digest,
        dependency_lock_sha256=lock_digest,
        sbom_sha256=sbom_digest,
        source_sha256=source_digest,
        created_at=created_at,
    )
    provenance_digest = sha256(provenance).hexdigest()

    manifest = ReleaseManifest(
        release_id=release_id,
        git_revision=git_revision,
        application_version=application_version,
        python_version=python_version,
        dependency_lock_sha256=lock_digest,
        sbom_sha256=sbom_digest,
        provenance_sha256=provenance_digest,
        state_schema_min=state_schema_min,
        state_schema_max=state_schema_max,
        fleet_protocol_version=fleet_protocol_version,
        fleet_agent_version=fleet_agent_version,
        constitution_sha256=constitution_sha256,
        configuration_schema_version=configuration_schema_version,
        created_at=created_at,
        artifact_sha256=artifact_digest,
        parent_release_id=parent_release_id,
        parent_manifest_sha256=parent_manifest_sha256,
        model_id=model_id,
        model_sha256=model_sha256,
        asset_sha256=asset_sha256,
    )

    lock_out = output_dir / "requirements.lock"
    sbom_out = output_dir / "sbom.cdx.json"
    provenance_out = output_dir / "provenance.intoto.json"
    manifest_out = output_dir / "release-manifest.json"

    lock_out.write_bytes(lock_bytes)
    sbom_out.write_bytes(sbom)
    provenance_out.write_bytes(provenance)
    manifest_out.write_bytes(manifest.canonical_bytes())

    return SupplyChainArtifacts(
        manifest_path=manifest_out,
        sbom_path=sbom_out,
        provenance_path=provenance_out,
        dependency_lock_path=lock_out,
        artifact_path=artifact_out,
        manifest=manifest,
    )


def verify_release_evidence(root: Path) -> ReleaseManifest:
    if not isinstance(root, Path) or not root.is_dir():
        raise FileNotFoundError("release evidence directory does not exist")
    manifest = ReleaseManifest.from_canonical_bytes(
        (root / "release-manifest.json").read_bytes()
    )
    lock = canonical_dependency_lock(root / "requirements.lock")
    sbom = (root / "sbom.cdx.json").read_bytes()
    provenance = (root / "provenance.intoto.json").read_bytes()

    if sha256(lock).hexdigest() != manifest.dependency_lock_sha256:
        raise ValueError("dependency lock digest mismatch")
    if sha256(sbom).hexdigest() != manifest.sbom_sha256:
        raise ValueError("SBOM digest mismatch")
    if sha256(provenance).hexdigest() != manifest.provenance_sha256:
        raise ValueError("provenance digest mismatch")

    artifact_dir = root / "artifact"
    if not artifact_dir.is_dir():
        raise ValueError("release evidence artifact directory is missing")
    wheels = tuple(artifact_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("release artifact must contain exactly one wheel")
    verify_wheel_identity(wheels[0])
    if directory_sha256(artifact_dir) != manifest.artifact_sha256:
        raise ValueError("release artifact digest mismatch")
    return manifest
