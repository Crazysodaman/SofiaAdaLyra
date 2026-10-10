from datetime import datetime, timezone
from pathlib import Path

import pytest

from sofia.creative import (
    ArtifactKind, CreativeProject, CreativeRequest, CreativeService,
    CreativeStore, CreativeWorkspaceManager, DevCandidateArtifactAdapter,
    ManagedAssetStore, NativeCreativeAdapter, CreativeExplorer,
    CreativeWorldBridge,
)
from sofia.interaction.world_model import ObjectKind, Transform
from sofia.interaction.world_store import VirtualWorldStore


NOW = datetime(2026, 10, 10, 13, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_dev, pytest.mark.pkg_integrate]


def infrastructure(tmp_path):
    store = CreativeStore(tmp_path / "sofia.db")
    store.create_project(CreativeProject(
        "fox-den", "Fox Den", "person:sparks", "local:text", NOW,
    ))
    return store, CreativeService(
        store, CreativeWorkspaceManager(tmp_path / "workspaces"),
        ManagedAssetStore(tmp_path / "assets", max_asset_bytes=2_000_000),
    )


def request(kind, *, artifact_id="artifact-1", specification=None):
    return CreativeRequest(
        f"request-{artifact_id}", "fox-den", artifact_id, kind,
        f"A {kind.value} artifact", "person:sparks", "sofia", "local:text",
        "CC-BY-4.0", specification or {}, f"goal:create:{artifact_id}",
    )


@pytest.mark.parametrize(
    ("kind", "specification", "media_prefix"),
    [
        (ArtifactKind.TEXT, {"content": "A verified note."}, "text/plain"),
        (ArtifactKind.STORY, {"content": "# A small story"}, "text/markdown"),
        (ArtifactKind.ART, {"color": "#3A245C"}, "image/svg+xml"),
        (ArtifactKind.MODEL_3D, {}, "model/obj"),
        (ArtifactKind.ANIMATION, {"frames": [0, 1]}, "application/"),
        (ArtifactKind.MUSIC, {"frequency_hz": 440}, "audio/wav"),
        (ArtifactKind.GAME, {"rules": ["explore"]}, "application/"),
        (ArtifactKind.SIMULATION, {"ticks": 10}, "application/"),
    ],
)
def test_native_adapter_produces_real_hashed_restart_safe_artifacts(
    tmp_path, kind, specification, media_prefix,
):
    store, service = infrastructure(tmp_path)
    artifact_id = f"artifact-{kind.value}"
    revision = service.create(
        request(kind, artifact_id=artifact_id, specification=specification),
        NativeCreativeAdapter(), now=NOW,
    )

    assert revision.media_type.startswith(media_prefix)
    assert len(revision.content_sha256) == 64
    assert Path(revision.content_path).is_file()
    assert revision.author_principal_id == "sofia"
    assert CreativeStore(store.path).latest(
        artifact_id, "person:sparks", "local:text",
    ) == revision


def test_artifact_revision_history_and_scope_isolation(tmp_path):
    store, service = infrastructure(tmp_path)
    first = service.create(
        request(ArtifactKind.TEXT, specification={"content": "v1"}),
        NativeCreativeAdapter(), now=NOW,
    )
    second = service.create(
        request(ArtifactKind.TEXT, specification={"content": "v2"}),
        NativeCreativeAdapter(), now=NOW,
    )
    assert [item.revision for item in store.history(
        "artifact-1", "person:sparks", "local:text",
    )] == [1, 2]
    assert first.content_sha256 != second.content_sha256
    assert store.latest("artifact-1", "person:sparks", "public") is None
    assert [project.project_id for project in store.list_projects(
        "person:sparks", "local:text",
    )] == ["fox-den"]
    assert store.list_projects("person:other", "local:text") == ()


def test_code_adapter_imports_only_governed_dev_candidate(tmp_path):
    store, service = infrastructure(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    adapter = DevCandidateArtifactAdapter(candidate, "dev-receipt:123")
    revision = service.create(
        request(
            ArtifactKind.CODE, artifact_id="code-feature",
            specification={"candidate_path": "feature.py"},
        ), adapter, now=NOW,
    )
    assert revision.source_receipt_id == "dev-receipt:123"
    assert revision.tool_id == "creative.dev-candidate"

    with pytest.raises(PermissionError, match="escapes"):
        service.create(
            request(
                ArtifactKind.CODE, artifact_id="code-escape",
                specification={"candidate_path": "../outside.py"},
            ), adapter, now=NOW,
        )


def test_unavailable_or_wrong_adapter_fails_without_inventory_record(tmp_path):
    store, service = infrastructure(tmp_path)
    with pytest.raises(RuntimeError, match="unavailable"):
        service.create(
            request(ArtifactKind.CODE), NativeCreativeAdapter(), now=NOW,
        )
    assert store.latest("artifact-1", "person:sparks", "local:text") is None


def test_project_scope_and_resource_limits_are_enforced(tmp_path):
    _store, service = infrastructure(tmp_path)
    too_large = "x" * 2_100_000
    with pytest.raises(RuntimeError, match="per-asset"):
        service.create(
            request(ArtifactKind.TEXT, specification={"content": too_large}),
            NativeCreativeAdapter(), now=NOW,
        )
    wrong = request(ArtifactKind.TEXT, artifact_id="wrong", specification={"content": "x"})
    wrong = CreativeRequest(
        wrong.request_id, wrong.project_id, wrong.artifact_id, wrong.kind,
        wrong.title, "other-owner", wrong.author_principal_id, wrong.audience_id,
        wrong.license_id, wrong.specification, wrong.evidence_ref,
    )
    with pytest.raises(KeyError, match="unavailable"):
        service.create(wrong, NativeCreativeAdapter(), now=NOW)


def test_artifact_identity_cannot_move_between_projects(tmp_path):
    store, service = infrastructure(tmp_path)
    service.create(
        request(ArtifactKind.TEXT, specification={"content": "first"}),
        NativeCreativeAdapter(), now=NOW,
    )
    store.create_project(CreativeProject(
        "other-project", "Other", "person:sparks", "local:text", NOW,
    ))
    original = request(ArtifactKind.TEXT, specification={"content": "second"})
    moved = CreativeRequest(
        "request-moved", "other-project", original.artifact_id, original.kind,
        original.title, original.owner_principal_id, original.author_principal_id,
        original.audience_id, original.license_id, original.specification,
        original.evidence_ref,
    )
    with pytest.raises(ValueError, match="another project"):
        service.create(moved, NativeCreativeAdapter(), now=NOW)


def test_explorer_verifies_preview_and_recovers_prior_revision(tmp_path):
    store, service = infrastructure(tmp_path)
    first = service.create(
        request(ArtifactKind.TEXT, specification={"content": "first"}),
        NativeCreativeAdapter(), now=NOW,
    )
    service.create(
        request(ArtifactKind.TEXT, specification={"content": "second"}),
        NativeCreativeAdapter(), now=NOW,
    )
    explorer = CreativeExplorer(store)
    path, media_type = explorer.verified_preview(
        "artifact-1", owner_principal_id="person:sparks", audience_id="local:text",
    )
    assert path.is_file() and media_type == "text/plain"
    recovered = explorer.recover(
        "artifact-1", target_revision=1, owner_principal_id="person:sparks",
        audience_id="local:text", evidence_ref="owner:recover", now=NOW,
    )
    assert recovered.revision == 3
    assert recovered.content_sha256 == first.content_sha256


def test_verified_authored_object_can_be_placed_in_world(tmp_path):
    store, service = infrastructure(tmp_path)
    artifact = service.create(
        request(ArtifactKind.MODEL_3D, artifact_id="fox-cube"),
        NativeCreativeAdapter(), now=NOW,
    )
    world = VirtualWorldStore(tmp_path / "sofia.db")
    world.ensure_foundation(
        owner_principal_id="sofia", audience_id="local:text", now=NOW,
    )
    receipt = CreativeWorldBridge(store, world).place(
        artifact_id=artifact.artifact_id,
        artifact_owner_principal_id="person:sparks",
        world_owner_principal_id="sofia", audience_id="local:text",
        object_id="fox-cube-object", object_name="Fox Cube",
        object_kind=ObjectKind.ART, space_id="sofia-studio",
        transform=Transform(x=2), actor_principal_id="person:sparks",
        evidence_ref="creative:place", now=NOW,
    )
    placed = world.get_object("fox-cube-object", "sofia", "local:text")
    assert receipt.action == "create"
    assert placed.asset_id == "artifact:fox-cube:r1"
    assert placed.state["artifact_sha256"] == artifact.content_sha256
