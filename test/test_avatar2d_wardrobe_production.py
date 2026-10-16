"""Account for the whole canonical wardrobe, never fabricate final art or grants."""
import json

import pytest

from sofia.avatar.presentation import PrivatePresentationGrant
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


def test_protected_details_fail_closed_without_valid_live_owner_grant():
    with pytest.raises(PermissionError):
        protected_work_orders(grant=None)
    invalid = PrivatePresentationGrant(
        adult_verified=False,
        owner_verified=True,
        private_session=True,
        explicit_current_opt_in=True,
        external_stop_active=False,
    )
    with pytest.raises(PermissionError):
        protected_work_orders(grant=invalid)
    stopped = PrivatePresentationGrant(
        adult_verified=True,
        owner_verified=True,
        private_session=True,
        explicit_current_opt_in=True,
        external_stop_active=True,
    )
    with pytest.raises(PermissionError):
        protected_work_orders(grant=stopped)
    authorized = PrivatePresentationGrant(
        adult_verified=True,
        owner_verified=True,
        private_session=True,
        explicit_current_opt_in=True,
        external_stop_active=False,
    )
    selected = protected_work_orders(grant=authorized)
    assert len(selected) == 51
    assert all(item.private_only for item in selected)
    assert all(len(item.source_sha256) == 64 for item in selected)
