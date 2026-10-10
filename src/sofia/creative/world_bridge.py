"""Place verified creative artifacts into canonical virtual-world metadata."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path

from sofia.interaction.world_model import ObjectKind, Transform, WorldObject
from sofia.interaction.world_store import VirtualWorldStore

from .store import CreativeStore


class CreativeWorldBridge:
    def __init__(self, artifacts: CreativeStore, world: VirtualWorldStore) -> None:
        self.artifacts, self.world = artifacts, world

    def place(
        self, *, artifact_id: str, artifact_owner_principal_id: str,
        world_owner_principal_id: str, audience_id: str, object_id: str,
        object_name: str, object_kind: ObjectKind, space_id: str,
        transform: Transform, actor_principal_id: str,
        evidence_ref: str, now: datetime,
    ):
        artifact = self.artifacts.latest(
            artifact_id, artifact_owner_principal_id, audience_id,
        )
        if artifact is None:
            raise KeyError("creative artifact unavailable in this scope")
        path = Path(artifact.content_path)
        digest = sha256()
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("creative artifact bytes failed placement verification")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != artifact.content_sha256:
            raise RuntimeError("creative artifact bytes failed placement verification")
        value = WorldObject(
            object_id=object_id, name=object_name, kind=object_kind,
            owner_principal_id=world_owner_principal_id,
            audience_id=audience_id, space_id=space_id, transform=transform,
            asset_id=f"artifact:{artifact.artifact_id}:r{artifact.revision}",
            state={
                "artifact_sha256": artifact.content_sha256,
                "media_type": artifact.media_type,
                "artifact_revision": artifact.revision,
            },
        )
        return self.world.add_object(
            value, actor_principal_id=actor_principal_id,
            evidence_ref=evidence_ref, now=now,
        )
