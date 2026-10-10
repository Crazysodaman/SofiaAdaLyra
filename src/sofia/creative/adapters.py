"""Typed authoring adapters. Code remains behind DEV/OpenCode receipts."""
from __future__ import annotations

from dataclasses import dataclass
import json
from math import pi, sin
from pathlib import Path
import shutil
import struct
import wave
import re

from .model import (
    ArtifactKind, CreativeRequest, CreativeToolProbe, GeneratedArtifact,
)


class NativeCreativeAdapter:
    adapter_id = "creative.native"
    version = "1.0"
    supported = (
        ArtifactKind.TEXT, ArtifactKind.ART, ArtifactKind.MODEL_3D,
        ArtifactKind.ANIMATION, ArtifactKind.MUSIC, ArtifactKind.STORY,
        ArtifactKind.GAME, ArtifactKind.SIMULATION,
    )

    def probe(self) -> CreativeToolProbe:
        return CreativeToolProbe(
            self.adapter_id, self.version, self.supported, True,
            "stdlib deterministic authoring adapter available",
        )

    def create(self, request: CreativeRequest, workspace: Path) -> GeneratedArtifact:
        if request.kind not in self.supported:
            raise ValueError("native adapter does not support requested artifact kind")
        workspace.mkdir(parents=True, exist_ok=True)
        if request.kind in {ArtifactKind.TEXT, ArtifactKind.STORY}:
            content = request.specification.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("text/story creation requires nonempty content")
            suffix = ".md" if request.kind is ArtifactKind.STORY else ".txt"
            name = f"artifact{suffix}"
            (workspace / name).write_text(content, encoding="utf-8")
            return GeneratedArtifact(name, "text/markdown" if suffix == ".md" else "text/plain",
                                     self.adapter_id, self.version, test_summary="UTF-8 roundtrip passed")
        if request.kind is ArtifactKind.ART:
            color = request.specification.get("color", "#3A245C")
            if not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
                raise ValueError("art color must be a six-digit hexadecimal color")
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" '
                'viewBox="0 0 512 512"><rect width="512" height="512" fill="#10131a"/>'
                f'<circle cx="256" cy="256" r="170" fill="{color}"/>'
                '<path d="M130 205 L185 65 L235 205 M277 205 L327 65 L382 205" '
                'fill="#8B1E3F"/><circle cx="210" cy="255" r="14" fill="#19D3C5"/>'
                '<circle cx="302" cy="255" r="14" fill="#19D3C5"/></svg>'
            )
            (workspace / "art.svg").write_text(svg, encoding="utf-8")
            return GeneratedArtifact("art.svg", "image/svg+xml", self.adapter_id, self.version,
                                     preview_filename="art.svg", test_summary="generated bounded SVG")
        if request.kind is ArtifactKind.MODEL_3D:
            obj = """o cube
v -1 -1 -1
v 1 -1 -1
v 1 1 -1
v -1 1 -1
v -1 -1 1
v 1 -1 1
v 1 1 1
v -1 1 1
f 1 2 3 4
f 5 8 7 6
f 1 5 6 2
f 2 6 7 3
f 3 7 8 4
f 5 1 4 8
"""
            (workspace / "model.obj").write_text(obj, encoding="ascii")
            return GeneratedArtifact("model.obj", "model/obj", self.adapter_id, self.version,
                                     test_summary="8 vertices and 6 faces generated")
        if request.kind is ArtifactKind.MUSIC:
            frequency = float(request.specification.get("frequency_hz", 440.0))
            if not 40 <= frequency <= 4000:
                raise ValueError("frequency_hz must be in 40..4000")
            path = workspace / "music.wav"
            rate, frames = 16_000, 8_000
            with wave.open(str(path), "wb") as stream:
                stream.setparams((1, 2, rate, frames, "NONE", "not compressed"))
                for index in range(frames):
                    sample = int(8_000 * sin(2 * pi * frequency * index / rate))
                    stream.writeframesraw(struct.pack("<h", sample))
            return GeneratedArtifact("music.wav", "audio/wav", self.adapter_id, self.version,
                                     test_summary="WAV header and bounded samples generated")
        payload = {
            "schema": f"sofia.{request.kind.value}.v1",
            "title": request.title,
            "specification": dict(request.specification),
        }
        name = f"{request.kind.value}.json"
        (workspace / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        media = f"application/vnd.sofia.{request.kind.value}+json"
        return GeneratedArtifact(name, media, self.adapter_id, self.version,
                                 test_summary="schema payload serialized and parsed")


@dataclass(slots=True)
class DevCandidateArtifactAdapter:
    """Import code only from an already governed DEV candidate receipt."""
    approved_root: Path
    candidate_receipt_id: str
    adapter_id: str = "creative.dev-candidate"
    version: str = "1.0"

    def probe(self) -> CreativeToolProbe:
        available = self.approved_root.is_dir() and bool(self.candidate_receipt_id.strip())
        return CreativeToolProbe(
            self.adapter_id, self.version, (ArtifactKind.CODE,), available,
            "governed DEV candidate workspace available" if available
            else "DEV candidate workspace/receipt unavailable",
        )

    def create(self, request: CreativeRequest, workspace: Path) -> GeneratedArtifact:
        if request.kind is not ArtifactKind.CODE:
            raise ValueError("DEV adapter supports code artifacts only")
        relative = request.specification.get("candidate_path")
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError("candidate_path must be a relative reviewed path")
        source = (self.approved_root / relative).resolve()
        root = self.approved_root.resolve()
        if root not in source.parents or not source.is_file():
            raise PermissionError("candidate_path escapes approved DEV workspace")
        workspace.mkdir(parents=True, exist_ok=True)
        destination = workspace / source.name
        shutil.copyfile(source, destination)
        return GeneratedArtifact(
            destination.name, "text/x-python", self.adapter_id, self.version,
            test_summary="imported from governed DEV candidate",
            source_receipt_id=self.candidate_receipt_id,
        )
