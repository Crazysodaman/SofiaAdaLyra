"""Account for the whole canonical wardrobe, never fabricate final art or grants."""
import json

import pytest

from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.core.social.principals import local_sparks_principal
from test.owner_auth_fixture import private_with_signed_owner
from sofia.avatar.vtuber_wardrobe_production import (
    canonical_json_wardrobe_records,
    export_public_production_queue,
    protected_work_orders,
    wardrobe_production_coverage,
    wardrobe_production_queue,
)


def test_all_source_json_garments_are_accounted_for_exactly_once():
    source = canonical_json_wardrobe_records()
    queue = wardrobe_production_queue()
    coverage = wardrobe_production_coverage(queue)
    ids = [item.item_id for item in queue]
    assert len(source) == len(queue) == coverage.total == 295
    assert len(set(ids)) == 295
    assert coverage.public == 244
    assert coverage.private == 51
    assert coverage.public + coverage.private == coverage.total
    assert len(coverage.by_source) == 14
    assert sum(count for _, count in coverage.by_source) == 295
    assert all(item.status == "source_brief_ready_art_unverified" for item in queue)
    assert all(len(item.source_sha256) == 64 for item in queue)


def test_waist_up_visibility_and_back_art_requirements_from_real_metadata():
    records = {item.item_id: item for item in wardrobe_production_queue()}
    top = records["day.technical_top"]
    jacket = records["day.engineer_jacket"]
    lounge = records["night.lounge_tee"]
    assert top.waist_up_visible
    assert jacket.waist_up_visible
    assert lounge.waist_up_visible
    assert jacket.required_views == ("front", "back")
    assert lounge.required_views == ("front", "back")
    assert any(not x.waist_up_visible for x in records.values())


def test_public_queue_lists_all_public_items_and_only_aggregates_private(tmp_path):
    output = tmp_path / "art-queue.json"
    coverage = export_public_production_queue(output)
    obj = json.loads(output.read_text("utf-8"))
    assert obj["schema"] == "sofia.avatar2d.production_queue.v1"
    assert obj["coverage"]["total"] == 295
    assert obj["coverage"]["private"] == 51
    assert len(obj["public_items"]) == coverage.public
    assert len({item["item_id"] for item in obj["public_items"]}) == 244
    assert obj["private_work_orders"]["count"] == 51
    assert "private_items" not in obj
    assert "private_sheer" not in output.read_text("utf-8")
    assert "private_rope" not in output.read_text("utf-8")
    assert obj["completion_state"] == "source_coverage_only_no_final_sprite_claims"
    with pytest.raises(ValueError):
        export_public_production_queue(output)


def test_protected_details_fail_closed_without_actual_durable_safe_permissions(tmp_path):
    state=bootstrap_canonical_sqlite(tmp_path/"sofia.db")
    store=PermissionStore(state)
    resolver=PrivatePresentationGrantResolver(state_path=state)
    principal=local_sparks_principal()
    with pytest.raises(PermissionError):
        protected_work_orders(
            resolver=resolver, principal=principal,
            explicit_current_opt_in=True,
        )
    private_with_signed_owner(
        store,private_chat=True,adult_chat=False,
        adult_avatar=True,adult_external_delivery=False,
    )
    with pytest.raises(PermissionError):
        protected_work_orders(
            resolver=resolver,principal=principal,
            explicit_current_opt_in=False,
        )
    selected=protected_work_orders(
        resolver=resolver,principal=principal,
        explicit_current_opt_in=True,
    )
    assert len(selected)==51
    assert all(item.private_only for item in selected)
    assert all(len(item.source_sha256)==64 for item in selected)
    private_with_signed_owner(
        store,private_chat=True,adult_chat=False,
        adult_avatar=False,adult_external_delivery=False,
    )
    with pytest.raises(PermissionError):
        protected_work_orders(
            resolver=resolver,principal=principal,
            explicit_current_opt_in=True,
        )
