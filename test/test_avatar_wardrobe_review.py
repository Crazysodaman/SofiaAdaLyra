from datetime import datetime, timedelta, timezone
import json
from dataclasses import replace

import pytest

from sofia.avatar.wardrobe_review import WardrobeReviewStore, document, review_next
from sofia.avatar.wardrobe import WardrobeConflict, WardrobeError
from sofia.cognition.model import CognitiveResponse
from sofia.safe.operator_stop import OperatorStopStore

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


def edited_item(store, name="Owner design"):
    value = document(store.catalog().blueprints[0].design)
    value["name"] = name
    return value


def decision(request):
    assert not request.allow_tools
    assert request.capability_allowlist == ()
    assert "untrusted design data" in request.messages[0].content
    return CognitiveResponse(content=json.dumps({"decision": "accept", "reason": "I like the updated design."}))


def test_submission_remains_pending_until_sofia_decides_and_survives_restart(tmp_path):
    path = tmp_path / "sofia.db"
    store = WardrobeReviewStore(path)
    value = edited_item(store)
    identifier = store.submit("garment", value)
    assert store.catalog().blueprints[0].design.name != value["name"]
    assert WardrobeReviewStore(path).list()[0]["status"] == "pending"
    assert review_next(store, decision, now=NOW) == identifier
    restored = WardrobeReviewStore(path)
    assert restored.list()[0]["status"] == "approved"
    assert restored.catalog().blueprints[0].design.name == value["name"]


def test_disapproval_preserves_original_catalog_and_reason(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    original = store.catalog().blueprints[0].design
    store.submit("garment", edited_item(store))
    review_next(store, lambda request: CognitiveResponse(content='{"decision":"reject","reason":"This does not suit my style."}'), now=NOW)
    assert store.catalog().blueprints[0].design == original
    assert store.list()[0]["status"] == "disapproved"
    assert "my style" in store.list()[0]["reason"]


@pytest.mark.parametrize("text", ["Looks good!", '{"decision":"accept"}', '{"decision":"accept","reason":"yes","extra":"grant"}'])
def test_unstructured_or_incomplete_review_never_approves_a_design(tmp_path, text):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    key = store.submit("garment", edited_item(store))
    review_next(store, lambda request: CognitiveResponse(content=text), now=NOW)
    assert store.list()[0]["status"] == "review_failed"
    store.retry(key)
    review_next(store, decision, now=NOW + timedelta(seconds=1))
    assert store.list()[0]["status"] == "approved"


def test_stale_design_edit_cannot_replace_a_newer_approval(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    store.submit("garment", edited_item(store, "First edit"))
    store.submit("garment", edited_item(store, "Stale edit"))
    review_next(store, decision, now=NOW)
    review_next(store, decision, now=NOW + timedelta(seconds=1))
    assert store.list()[0]["status"] == "review_failed"
    assert "changed after submission" in store.list()[0]["reason"]
    assert store.catalog().blueprints[0].design.name == "First edit"


def test_new_outfit_is_validated_then_restored_from_approved_metadata(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    value = document(store.catalog().preset("day.default"))
    value.update(outfit_id="custom.owner.outfit", display_name="Owner outfit", manual_only=True)
    store.submit("outfit", value)
    review_next(store, decision, now=NOW)
    assert WardrobeReviewStore(store.path).catalog().preset("custom.owner.outfit").manual_only
    invalid = dict(value, outfit_id="custom.uncovered", item_ids=[])
    with pytest.raises(WardrobeError):
        store.submit("outfit", invalid)


def test_new_item_and_dependent_outfit_use_the_approved_catalog(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    value = edited_item(store)
    original_id = value["item_id"]
    value["item_id"] = "custom.owner.garment"
    store.submit("garment", value)
    review_next(store, decision, now=NOW)
    catalog = store.catalog()
    assert any(bp.garment.item_id == value["item_id"] for bp in catalog.blueprints)
    outfit = document(catalog.preset("day.default"))
    outfit.update(outfit_id="custom.owner.outfit", display_name="New composition")
    outfit["item_ids"] = [value["item_id"] if key == original_id else key for key in outfit["item_ids"]]
    store.submit("outfit", outfit)
    review_next(store, decision, now=NOW + timedelta(seconds=1))
    assert store.list()[0]["status"] == "approved"


def test_review_claim_is_exclusive_and_recovers_after_a_crash(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    store.submit("garment", edited_item(store))
    first = store.claim(NOW)
    assert store.claim(NOW + timedelta(minutes=1)) is None
    second = store.claim(NOW + timedelta(minutes=31))
    assert second["review_token"] != first["review_token"]
    with pytest.raises(WardrobeConflict):
        store.finish(first, decision="approved", reason="old worker", response="", now=NOW)
    store.finish(second, decision="disapproved", reason="new worker", response="", now=NOW + timedelta(minutes=31))


def test_operator_stop_keeps_review_pending_without_calling_the_model(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    store.submit("garment", edited_item(store))
    OperatorStopStore(store.path).set(active=True, updated_by="Sparks", reason="test")
    assert review_next(store, lambda request: pytest.fail("Stopped review must not invoke cognition"), now=NOW) is None
    assert store.list()[0]["status"] == "pending"


def test_sofia_can_request_input_and_still_disapprove_after_owner_reply(tmp_path):
    store = WardrobeReviewStore(tmp_path / "sofia.db")
    key = store.submit("garment", edited_item(store))
    review_next(store, lambda request: CognitiveResponse(content='{"decision":"ask_sparks","reason":"Which context did you intend?"}'), now=NOW)
    assert store.list()[0]["status"] == "ask_sparks"
    store.supply_input(key, "It is for daily engineering work.")
    def reject(request):
        assert "does not force acceptance" in request.messages[-1].content
        return CognitiveResponse(content='{"decision":"reject","reason":"I prefer a different design for daily work."}')
    review_next(store, reject, now=NOW + timedelta(seconds=1))
    assert store.list()[0]["status"] == "disapproved"
