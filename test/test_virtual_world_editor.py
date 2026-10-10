from datetime import datetime, timezone

import pytest

from sofia.interaction.world_editor import WorldEditor
from sofia.interaction.world_model import ObjectKind, Transform, WorldObject
from sofia.interaction.world_store import VirtualWorldStore
from sofia.social.model import AudienceKind, PrincipalContext


NOW = datetime(2026, 10, 10, 11, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_interact, pytest.mark.pkg_avatar, pytest.mark.pkg_ui]


def setup_world(tmp_path):
    world = VirtualWorldStore(tmp_path / "sofia.db")
    principal = PrincipalContext(
        "person:sparks", "local:text", AudienceKind.PRIVATE, "Sparks",
    )
    world.ensure_foundation(
        owner_principal_id="sofia", audience_id=principal.audience_id, now=NOW,
    )
    editor = WorldEditor(world, principal=principal, owner_principal_id="sofia")
    return world, editor


def test_authenticated_editor_renames_archives_and_restores_with_history(tmp_path):
    world, editor = setup_world(tmp_path)
    editor.rename_space(
        "sofia-studio", "Foxfire Studio", expected_revision=1,
        evidence_ref="message:rename", now=NOW,
    )
    editor.archive_space(
        "sofia-studio", expected_revision=2,
        evidence_ref="message:archive", now=NOW,
    )
    assert "sofia-studio" not in {
        item.space_id for item in world.list_spaces("sofia", "local:text")
    }
    editor.archive_space(
        "sofia-studio", expected_revision=3,
        evidence_ref="message:restore", now=NOW, archived=False,
    )
    current = world.get_space("sofia-studio", "sofia", "local:text")
    assert (current.name, current.archived, current.revision) == (
        "Foxfire Studio", False, 4,
    )
    assert [item["action"] for item in world.history("space", "sofia-studio")] == [
        "initialize", "edit", "archive", "restore",
    ]


def test_stale_editor_revision_cannot_overwrite_newer_arrangement(tmp_path):
    world, editor = setup_world(tmp_path)
    world.add_object(
        WorldObject(
            "desk", "Workbench", ObjectKind.FURNITURE, "sofia", "local:text",
            "engineering-workshop", Transform(),
        ),
        actor_principal_id="person:sparks", evidence_ref="test:add", now=NOW,
    )
    editor.arrange(
        "desk", Transform(x=5, yaw=90), expected_revision=1,
        evidence_ref="test:move", now=NOW,
    )
    with pytest.raises(RuntimeError, match="revision changed"):
        editor.arrange(
            "desk", Transform(x=9), expected_revision=1,
            evidence_ref="test:stale", now=NOW,
        )
    assert world.get_object("desk", "sofia", "local:text").transform.x == 5


def test_inventory_grouping_and_connections_are_canonical_mutations(tmp_path):
    world, _editor = setup_world(tmp_path)
    connection = world.connect_spaces(
        connection_id="studio-to-garden", source_space_id="sofia-studio",
        target_space_id="shared-garden", owner_principal_id="sofia",
        audience_id="local:text", kind="door", label="Garden door",
        actor_principal_id="person:sparks", evidence_ref="test:connect", now=NOW,
    )
    assert connection.action == "connect"
    world.add_object(
        WorldObject(
            "bookcase", "Bookcase", ObjectKind.CONTAINER, "sofia", "local:text",
            "sofia-studio", Transform(),
        ), actor_principal_id="person:sparks", evidence_ref="test:add", now=NOW,
    )
    world.add_object(
        WorldObject(
            "manual", "Electronics Manual", ObjectKind.BOOK, "sofia", "local:text",
            "sofia-studio", Transform(), container_id="bookcase", group_id="reference-books",
        ), actor_principal_id="person:sparks", evidence_ref="test:add", now=NOW,
    )
    assert [item.object_id for item in world.inventory(
        "bookcase", "sofia", "local:text",
    )] == ["manual"]
    assert world.scene("sofia-studio", "sofia", "local:text").objects[0].object_id == "bookcase"


def test_object_interaction_only_acknowledges_exact_unchanged_scene_revision(tmp_path):
    world, editor = setup_world(tmp_path)
    world.add_object(
        WorldObject(
            "piano", "Piano", ObjectKind.INSTRUMENT, "sofia", "local:text",
            "sofia-studio", Transform(),
        ), actor_principal_id="person:sparks", evidence_ref="test:add", now=NOW,
    )
    decision = editor.interact(
        object_id="piano", verb="play", gesture="piano-playing",
        evidence_ref="message:play-piano", now=NOW,
    )
    receipt = editor.acknowledge(
        decision.interaction_id, rendered=True, backend="test-renderer",
        detail="animation frame committed", now=NOW,
    )
    assert receipt.acknowledged and receipt.status == "rendered"

    stale = editor.interact(
        object_id="piano", verb="inspect", gesture="lean-forward",
        evidence_ref="message:inspect", now=NOW,
    )
    editor.arrange(
        "piano", Transform(x=1), expected_revision=1,
        evidence_ref="message:move", now=NOW,
    )
    with pytest.raises(RuntimeError, match="changed"):
        editor.acknowledge(
            stale.interaction_id, rendered=True, backend="test-renderer",
            detail="late frame", now=NOW,
        )


def test_wrong_audience_cannot_edit_private_world(tmp_path):
    world, _editor = setup_world(tmp_path)
    wrong = WorldEditor(
        world,
        principal=PrincipalContext(
            "person:sparks", "discord:dm:1", AudienceKind.PRIVATE, "Sparks",
        ),
        owner_principal_id="sofia",
    )
    with pytest.raises(KeyError, match="unavailable"):
        wrong.rename_space(
            "sofia-studio", "Leaked", expected_revision=1,
            evidence_ref="wrong-audience", now=NOW,
        )


def test_undo_restores_prior_state_as_new_revision_and_import_is_atomic(tmp_path):
    world, editor = setup_world(tmp_path)
    world.add_object(
        WorldObject(
            "chair", "Chair", ObjectKind.FURNITURE, "sofia", "local:text",
            "sofia-studio", Transform(x=1),
        ), actor_principal_id="person:sparks", evidence_ref="test:add", now=NOW,
    )
    editor.arrange(
        "chair", Transform(x=8), expected_revision=1,
        evidence_ref="test:move", now=NOW,
    )
    receipt = world.undo(
        entity_type="object", entity_id="chair", target_revision=1,
        owner_principal_id="sofia", audience_id="local:text",
        expected_revision=2, actor_principal_id="person:sparks",
        evidence_ref="test:undo", now=NOW,
    )
    restored = world.get_object("chair", "sofia", "local:text")
    assert (restored.transform.x, restored.revision, receipt.action) == (
        1, 3, "undo-to-1",
    )

    imported = tuple(
        WorldObject(
            f"plant-{number}", f"Plant {number}", ObjectKind.PLANT,
            "sofia", "local:text", "shared-garden", Transform(x=number),
        )
        for number in range(3)
    )
    receipts = world.import_objects(
        imported, actor_principal_id="person:sparks",
        evidence_ref="import:reviewed-fixture", now=NOW,
    )
    assert len(receipts) == 3
    assert {item.object_id for item in world.scene(
        "shared-garden", "sofia", "local:text",
    ).objects} == {"plant-0", "plant-1", "plant-2"}


def test_import_reorders_valid_containers_and_rejects_cycles_atomically(tmp_path):
    world, _editor = setup_world(tmp_path)
    child = WorldObject(
        "stored-book", "Stored Book", ObjectKind.BOOK, "sofia", "local:text",
        "sofia-studio", Transform(), container_id="crate",
    )
    parent = WorldObject(
        "crate", "Crate", ObjectKind.CONTAINER, "sofia", "local:text",
        "sofia-studio", Transform(),
    )
    world.import_objects(
        (child, parent), actor_principal_id="person:sparks",
        evidence_ref="import:containers", now=NOW,
    )
    assert [item.object_id for item in world.inventory(
        "crate", "sofia", "local:text",
    )] == ["stored-book"]

    a = WorldObject(
        "cycle-a", "A", ObjectKind.CONTAINER, "sofia", "local:text",
        "sofia-studio", Transform(), container_id="cycle-b",
    )
    b = WorldObject(
        "cycle-b", "B", ObjectKind.CONTAINER, "sofia", "local:text",
        "sofia-studio", Transform(), container_id="cycle-a",
    )
    before = world.object_count()
    with pytest.raises(ValueError, match="cycle"):
        world.import_objects(
            (a, b), actor_principal_id="person:sparks",
            evidence_ref="import:cycle", now=NOW,
        )
    assert world.object_count() == before
