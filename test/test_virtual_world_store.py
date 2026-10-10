from datetime import datetime, timezone

import pytest

from sofia.interaction.world_model import ObjectKind, SpaceKind, Transform, WorldObject
from sofia.interaction.world_store import VirtualWorldStore


NOW = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
pytestmark = [pytest.mark.pkg_interact, pytest.mark.pkg_avatar]


def store(tmp_path, **limits):
    return VirtualWorldStore(tmp_path / "sofia.db", **limits)


def test_foundation_has_three_independent_spaces_and_survives_restart(tmp_path):
    world = store(tmp_path)
    spaces = world.ensure_foundation(
        owner_principal_id="sofia", audience_id="desktop-owner", now=NOW,
    )
    assert {item.space_id for item in spaces} == {
        "sofia-studio", "engineering-workshop", "shared-garden",
    }
    assert all(item.parent_space_id is None for item in spaces)

    restarted = store(tmp_path)
    repeated = restarted.ensure_foundation(
        owner_principal_id="sofia", audience_id="desktop-owner", now=NOW,
    )
    assert repeated == spaces
    assert len(restarted.list_spaces("sofia", "desktop-owner")) == 3


def test_spaces_are_strictly_principal_and_audience_scoped(tmp_path):
    world = store(tmp_path)
    world.ensure_foundation(owner_principal_id="sofia", audience_id="private-a", now=NOW)

    with pytest.raises(KeyError, match="unavailable"):
        world.get_space("sofia-studio", "sofia", "public")
    with pytest.raises(KeyError, match="unavailable"):
        world.get_space("sofia-studio", "sparks", "private-a")


def test_nested_space_and_object_have_durable_identity_transform_and_asset(tmp_path):
    world = store(tmp_path)
    world.ensure_foundation(owner_principal_id="sofia", audience_id="owner", now=NOW)
    receipt = world.create_space(
        space_id="electronics-bench", name="Electronics Bench", kind=SpaceKind.WORKSPACE,
        owner_principal_id="sofia", audience_id="owner",
        parent_space_id="engineering-workshop", actor_principal_id="sofia",
        evidence_ref="world:test:create-space", now=NOW,
    )
    assert receipt.revision == 1 and receipt.action == "create"

    value = WorldObject(
        object_id="scope-1", name="Oscilloscope", kind=ObjectKind.EQUIPMENT,
        owner_principal_id="sofia", audience_id="owner",
        space_id="electronics-bench", transform=Transform(1, 2, 3, yaw=45),
        asset_id="artifact:scope-model-v1", state={"power": "off"},
    )
    world.add_object(
        value, actor_principal_id="sofia", evidence_ref="world:test:add", now=NOW,
    )

    page = store(tmp_path).scene(
        "electronics-bench", "sofia", "owner", render_budget=10,
    )
    assert page.objects[0].object_id == "scope-1"
    assert page.objects[0].transform.yaw == 45
    assert page.objects[0].asset_id == "artifact:scope-model-v1"


def test_large_inventory_is_stored_but_scene_loading_is_bounded(tmp_path):
    world = store(tmp_path, max_objects=10_000, max_scene_page=75)
    world.ensure_foundation(owner_principal_id="sofia", audience_id="owner", now=NOW)
    with world._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        for number in range(2_500):
            object_id = f"book-{number:05d}"
            db.execute(
                """INSERT INTO world_object VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (object_id, f"Book {number}", ObjectKind.BOOK.value, "sofia", "owner",
                 "sofia-studio",
                 '{"pitch":0.0,"roll":0.0,"scale":1.0,"x":0.0,"y":0.0,"yaw":0.0,"z":0.0}',
                 None, None, None, "{}", 0, 1, NOW.isoformat(), NOW.isoformat()),
            )
    assert world.object_count() == 2_500

    first = world.scene("sofia-studio", "sofia", "owner", render_budget=50)
    second = world.scene(
        "sofia-studio", "sofia", "owner", cursor=first.next_cursor,
        render_budget=50,
    )
    assert first.total_stored == 2_500
    assert len(first.objects) == len(second.objects) == 50
    assert set(item.object_id for item in first.objects).isdisjoint(
        item.object_id for item in second.objects
    )
    with pytest.raises(ValueError, match="render_budget"):
        world.scene("sofia-studio", "sofia", "owner", render_budget=76)


def test_container_must_be_real_scoped_container(tmp_path):
    world = store(tmp_path)
    world.ensure_foundation(owner_principal_id="sofia", audience_id="owner", now=NOW)
    non_container = WorldObject(
        "lamp", "Lamp", ObjectKind.ELECTRONICS, "sofia", "owner",
        "sofia-studio", Transform(),
    )
    world.add_object(
        non_container, actor_principal_id="sofia", evidence_ref="test", now=NOW,
    )
    inside = WorldObject(
        "book", "Book", ObjectKind.BOOK, "sofia", "owner",
        "sofia-studio", Transform(), container_id="lamp",
    )
    with pytest.raises(ValueError, match="container object"):
        world.add_object(
            inside, actor_principal_id="sofia", evidence_ref="test", now=NOW,
        )
