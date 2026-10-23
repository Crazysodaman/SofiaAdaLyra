"""Privacy-scoped project explorer, preview verification, and recovery."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from .model import ArtifactRevision
from .store import CreativeStore


class CreativeExplorer:
    def __init__(self, store: CreativeStore) -> None:
        self.store = store

    def list_project(
        self, project_id: str, *, owner_principal_id: str, audience_id: str,
    ) -> tuple[ArtifactRevision, ...]:
        return self.store.list_project(project_id, owner_principal_id, audience_id)

    def history(
        self, artifact_id: str, *, owner_principal_id: str, audience_id: str,
    ) -> tuple[ArtifactRevision, ...]:
        return self.store.history(artifact_id, owner_principal_id, audience_id)

    def verified_preview(
        self, artifact_id: str, *, owner_principal_id: str, audience_id: str,
    ) -> tuple[Path, str]:
        revision = self.store.latest(artifact_id, owner_principal_id, audience_id)
        if revision is None:
            raise KeyError("artifact unavailable in this scope")
        path = Path(revision.content_path)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError("managed artifact bytes are unavailable")
        digest_value = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest_value.update(chunk)
        digest = digest_value.hexdigest()
        if digest != revision.content_sha256:
            raise RuntimeError("managed artifact failed preview integrity check")
        return path, revision.media_type

    def recover(
        self, artifact_id: str, *, target_revision: int,
        owner_principal_id: str, audience_id: str, evidence_ref: str,
        now: datetime,
    ) -> ArtifactRevision:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("recovery time must be timezone-aware")
        history = self.store.history(artifact_id, owner_principal_id, audience_id)
        target = next((item for item in history if item.revision == target_revision), None)
        if target is None:
            raise KeyError("artifact revision unavailable in this scope")
        current = history[-1]
        recovered = replace(
            target, revision=current.revision + 1,
            evidence_ref=evidence_ref,
            test_summary=(target.test_summary + f"; recovered from revision {target_revision}")[:1000],
            created_at=now.astimezone(timezone.utc),
        )
        self.store.append(recovered)
        return recovered
