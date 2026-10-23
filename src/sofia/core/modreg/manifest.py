"""Typed validation of Sofía module manifests.

Manifest files discovered on disk are UNTRUSTED CANDIDATES. Validation
here is only a filter: nothing below executes code, imports candidate
packages, or grants authority. A manifest becomes part of the trusted
registry only when the owner-session writer records it as verified.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import json
import re


_NAME = re.compile(
    r"^sofia\.[a-z][a-z0-9_]*([.][a-z][a-z0-9_]*)*$"
)
_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
_CAPABILITY = re.compile(
    r"^[a-z][a-z0-9_]*([.][a-z][a-z0-9_]*){1,3}$"
)


class ModuleManifestError(ValueError):
    """A manifest failed typed validation."""


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    """A validated module manifest (still verification-agnostic)."""

    name: str
    version: str
    purpose: str
    boundary_notes: str
    declared_capabilities: tuple[str, ...]
    declared_dependencies: tuple[str, ...]
    authority_boundary: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ModuleManifestError(
                "module name must be a sofia.* dotted package name"
            )
        if not isinstance(self.version, str) or _VERSION.fullmatch(
            self.version
        ) is None:
            raise ModuleManifestError("version must be semver X.Y.Z")
        for label, text in (
            ("purpose", self.purpose),
            ("boundary_notes", self.boundary_notes),
        ):
            if not isinstance(text, str) or not text.strip():
                raise ModuleManifestError(f"{label} must be nonempty text")
            if len(text.strip()) > 800:
                raise ModuleManifestError(f"{label} must be bounded (<=800)")
        if type(self.declared_capabilities) is not tuple:
            raise ModuleManifestError("declared_capabilities must be a tuple")
        if (
            len(self.declared_capabilities) > 32
            or len(set(self.declared_capabilities)) != len(
                self.declared_capabilities
            )
            or any(
                not isinstance(item, str)
                or _CAPABILITY.fullmatch(item) is None
                for item in self.declared_capabilities
            )
        ):
            raise ModuleManifestError(
                "declared_capabilities must be <=32 distinct dotted names"
            )
        if type(self.declared_dependencies) is not tuple:
            raise ModuleManifestError("declared_dependencies must be a tuple")
        if (
            len(self.declared_dependencies) > 32
            or len(set(self.declared_dependencies)) != len(
                self.declared_dependencies
            )
            or any(
                not isinstance(item, str) or _NAME.fullmatch(item) is None
                for item in self.declared_dependencies
            )
        ):
            raise ModuleManifestError(
                "declared_dependencies must be <=32 distinct sofia.* names"
            )
        if self.name in self.declared_dependencies:
            raise ModuleManifestError("a module cannot depend on itself")
        if not isinstance(self.authority_boundary, str) or not (
            self.authority_boundary.strip()
        ) or len(self.authority_boundary.strip()) > 160:
            raise ModuleManifestError(
                "authority_boundary must be bounded nonempty text"
            )

    @property
    def version_parts(self) -> tuple[int, int, int]:
        return tuple(int(part) for part in self.version.split("."))  # type: ignore[return-value]


def parse_manifest(document: object) -> ModuleManifest:
    """Validate an untrusted manifest document into a typed manifest."""
    if not isinstance(document, dict):
        raise ModuleManifestError("manifest must be a JSON object")
    try:
        purpose = document["purpose"]
        boundary_notes = document["boundary_notes"]
        capabilities = document["declared_capabilities"]
        dependencies = document["declared_dependencies"]
        authority_boundary = document["authority_boundary"]
    except KeyError as exc:
        raise ModuleManifestError(
            f"manifest field missing: {exc.args[0]}"
        ) from exc
    unexpected = set(document) - {
        "name",
        "version",
        "purpose",
        "boundary_notes",
        "declared_capabilities",
        "declared_dependencies",
        "authority_boundary",
    }
    if unexpected:
        raise ModuleManifestError(
            f"unexpected manifest fields: {sorted(unexpected)}"
        )
    for list_field in (capabilities, dependencies):
        if not isinstance(list_field, list) or any(
            not isinstance(item, str) for item in list_field
        ):
            raise ModuleManifestError("manifest lists must be arrays of strings")
    document_name = document.get("name")
    document_version = document.get("version")
    if not isinstance(document_name, str):
        raise ModuleManifestError("name must be a string")
    if not isinstance(document_version, str):
        raise ModuleManifestError("version must be a string")
    return ModuleManifest(
        name=document_name,
        version=document_version,
        purpose=purpose,
        boundary_notes=boundary_notes,
        declared_capabilities=tuple(capabilities),
        declared_dependencies=tuple(dependencies),
        authority_boundary=authority_boundary,
    )


def _candidate_files(root: Path) -> Iterator[Path]:
    packages = Path(root) / "src" / "sofia"
    if not packages.is_dir():
        return
    yield from sorted(
        path
        for path in packages.glob("*/module_manifest.json")
        if path.is_file()
    )


@dataclass(frozen=True, slots=True)
class ManifestCandidate:
    """A manifest file observed under the authorized codebase root."""

    path: Path
    manifest: ModuleManifest
    parse_error: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path must be a Path")
        if self.parse_error is None and not isinstance(
            self.manifest, ModuleManifest
        ):
            raise TypeError("candidate needs a manifest or a parse_error")


def discover_candidates(root: Path) -> tuple[ManifestCandidate, ...]:
    """Observe manifest documents under the authorized root.

    Discovery is observation only: candidates are returned, never
    registered, and any document that fails validation is returned as a
    candidate carrying its parse error instead of a manifest.
    """
    if not isinstance(root, Path):
        raise TypeError("root must be a Path")
    resolved = root.resolve()
    candidates: list[ManifestCandidate] = []
    for path in _candidate_files(resolved):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            candidates.append(
                ManifestCandidate(
                    path=path, manifest=parse_manifest(document),
                    parse_error=None,
                )
            )
        except (OSError, ValueError, ModuleManifestError) as exc:
            candidates.append(
                ManifestCandidate(
                    path=path, manifest=None,  # type: ignore[arg-type]
                    parse_error=f"{type(exc).__name__}: {exc}",
                )
            )
    return tuple(candidates)
