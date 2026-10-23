from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Mapping


CREATIVE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class ArtifactKind(str, Enum):
    TEXT = "text"
    CODE = "code"
    ART = "art"
    MODEL_3D = "model_3d"
    ANIMATION = "animation"
    MUSIC = "music"
    STORY = "story"
    GAME = "game"
    SIMULATION = "simulation"


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or CREATIVE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a canonical identifier")
    return value


def _text(value: str, label: str, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValueError(f"{label} must be bounded text")
    return value.strip()


@dataclass(frozen=True, slots=True)
class CreativeToolProbe:
    adapter_id: str
    version: str
    supported_kinds: tuple[ArtifactKind, ...]
    available: bool
    reason: str


@dataclass(frozen=True, slots=True)
class CreativeProject:
    project_id: str
    title: str
    owner_principal_id: str
    audience_id: str
    created_at: datetime
    archived: bool = False

    def __post_init__(self) -> None:
        _id(self.project_id, "project_id")
        _text(self.title, "project title")
        _id(self.owner_principal_id, "owner_principal_id")
        _text(self.audience_id, "audience_id", 160)
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

@dataclass(frozen=True, slots=True)
class CreativeRequest:
    request_id: str
    project_id: str
    artifact_id: str
    kind: ArtifactKind
    title: str
    owner_principal_id: str
    author_principal_id: str
    audience_id: str
    license_id: str
    specification: Mapping[str, object]
    evidence_ref: str

    def __post_init__(self) -> None:
        for value, label in ((self.request_id, "request_id"),
                             (self.project_id, "project_id"),
                             (self.artifact_id, "artifact_id"),
                             (self.owner_principal_id, "owner_principal_id"),
                             (self.author_principal_id, "author_principal_id")):
            _id(value, label)
        _text(self.title, "artifact title")
        _text(self.audience_id, "audience_id", 160)
        _text(self.license_id, "license_id", 120)
        _text(self.evidence_ref, "evidence_ref", 300)
        if not isinstance(self.kind, ArtifactKind) or not isinstance(self.specification, Mapping):
            raise TypeError("artifact kind/specification are invalid")


@dataclass(frozen=True, slots=True)
class GeneratedArtifact:
    filename: str
    media_type: str
    tool_id: str
    tool_version: str
    preview_filename: str | None = None
    test_summary: str = ""
    source_receipt_id: str | None = None

    def __post_init__(self) -> None:
        if (not self.filename or self.filename != self.filename.split("/")[-1]
                or "\\" in self.filename or self.filename in {".", ".."}):
            raise ValueError("generated filename must be a safe basename")
        _text(self.media_type, "media_type", 160)
        _id(self.tool_id, "tool_id")
        _text(self.tool_version, "tool_version", 120)


@dataclass(frozen=True, slots=True)
class ArtifactRevision:
    artifact_id: str
    project_id: str
    revision: int
    kind: ArtifactKind
    title: str
    content_sha256: str
    content_path: str
    media_type: str
    byte_size: int
    tool_id: str
    tool_version: str
    preview_sha256: str | None
    test_summary: str
    license_id: str
    author_principal_id: str
    audience_id: str
    evidence_ref: str
    source_receipt_id: str | None
    created_at: datetime

    def __post_init__(self) -> None:
        for value, label in (
            (self.artifact_id, "artifact_id"),
            (self.project_id, "project_id"),
            (self.author_principal_id, "author_principal_id"),
            (self.tool_id, "tool_id"),
        ):
            _id(value, label)
        if not isinstance(self.kind, ArtifactKind):
            raise TypeError("ArtifactKind required")
        if not isinstance(self.revision, int) or self.revision < 1:
            raise ValueError("artifact revision must be positive")
        _text(self.title, "artifact title")
        if re.fullmatch(r"[0-9a-f]{64}", self.content_sha256) is None:
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        if self.preview_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", self.preview_sha256) is None:
            raise ValueError("preview_sha256 must be a lowercase SHA-256 digest")
        _text(self.content_path, "content_path", 4096)
        _text(self.media_type, "media_type", 160)
        _text(self.tool_version, "tool_version", 120)
        _text(self.license_id, "license_id", 120)
        _text(self.audience_id, "audience_id", 160)
        _text(self.evidence_ref, "evidence_ref", 300)
        if not isinstance(self.byte_size, int) or self.byte_size <= 0:
            raise ValueError("byte_size must be positive")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
