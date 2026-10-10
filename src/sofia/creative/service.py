from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import shutil
from uuid import uuid4

from .model import ArtifactRevision, CreativeRequest, GeneratedArtifact
from .paths import path_component
from .store import CreativeStore


class CreativeWorkspaceManager:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def allocate(self, request: CreativeRequest) -> Path:
        project_component = path_component(request.project_id)
        request_component = path_component(request.request_id)
        path = self.root / project_component / f"{request_component}-{uuid4().hex[:8]}"
        try:
            path.resolve().relative_to(self.root.resolve())
        except ValueError as exc:
            raise PermissionError("creative workspace escaped its isolated root") from exc
        path.mkdir(parents=True, exist_ok=False)
        return path


class ManagedAssetStore:
    def __init__(
        self, root: Path | str, *, max_asset_bytes: int = 256 * 1024**2,
        max_total_bytes: int = 20 * 1024**3,
    ) -> None:
        self.root = Path(root)
        self.max_asset_bytes, self.max_total_bytes = max_asset_bytes, max_total_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest(path: Path) -> str:
        value = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    def import_file(self, source: Path) -> tuple[str, Path, int]:
        source = Path(source)
        if not source.is_file() or source.is_symlink():
            raise FileNotFoundError(source)
        size = source.stat().st_size
        if size <= 0 or size > self.max_asset_bytes:
            raise RuntimeError("creative asset violates per-asset resource limit")
        digest = self.digest(source)
        destination = self.root / digest[:2] / digest
        current = sum(
            item.stat().st_size for item in self.root.rglob("*")
            if item.is_file() and not item.is_symlink()
        )
        if not destination.exists() and current + size > self.max_total_bytes:
            raise RuntimeError("creative asset storage resource limit exceeded")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise RuntimeError("managed asset path is an unsafe symlink")
        if not destination.exists():
            temporary = destination.with_name(f".{digest}.{uuid4().hex}.tmp")
            shutil.copyfile(source, temporary)
            if self.digest(temporary) != digest:
                temporary.unlink(missing_ok=True)
                raise RuntimeError("managed asset failed post-copy hash verification")
            os.replace(temporary, destination)
        return digest, destination, size


class CreativeService:
    def __init__(
        self, store: CreativeStore, workspaces: CreativeWorkspaceManager,
        assets: ManagedAssetStore,
    ) -> None:
        self.store, self.workspaces, self.assets = store, workspaces, assets

    def create(self, request: CreativeRequest, adapter, *, now: datetime) -> ArtifactRevision:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("creative artifact time must be timezone-aware")
        project = self.store.project(
            request.project_id, request.owner_principal_id, request.audience_id,
        )
        if project.archived:
            raise ValueError("cannot create artifacts in an archived project")
        latest = self.store.latest(
            request.artifact_id, request.owner_principal_id, request.audience_id,
        )
        if latest is not None and latest.project_id != request.project_id:
            raise ValueError("artifact identity already belongs to another project")
        probe = adapter.probe()
        if not probe.available or request.kind not in probe.supported_kinds:
            raise RuntimeError(f"creative adapter unavailable: {probe.reason}")
        workspace = self.workspaces.allocate(request)
        generated = adapter.create(request, workspace)
        if not isinstance(generated, GeneratedArtifact):
            raise TypeError("creative adapter must return GeneratedArtifact")
        output = workspace / generated.filename
        try:
            output.resolve().relative_to(workspace.resolve())
        except ValueError as exc:
            raise PermissionError("creative output escaped isolated workspace") from exc
        digest, managed_path, size = self.assets.import_file(output)
        preview_digest = None
        if generated.preview_filename is not None:
            preview = workspace / generated.preview_filename
            preview_digest, _preview_path, _preview_size = self.assets.import_file(preview)
        revision = ArtifactRevision(
            request.artifact_id, request.project_id,
            1 if latest is None else latest.revision + 1,
            request.kind, request.title, digest, str(managed_path),
            generated.media_type, size, generated.tool_id, generated.tool_version,
            preview_digest, generated.test_summary[:1000], request.license_id,
            request.author_principal_id, request.audience_id, request.evidence_ref,
            generated.source_receipt_id, now.astimezone(timezone.utc),
        )
        self.store.append(revision)
        return revision
