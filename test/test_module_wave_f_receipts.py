"""Wave F receipts retain bounded evidence and never claim external effects."""
from datetime import datetime, timezone

from sofia.modules.calendar import review_schedule_conflicts
from sofia.modules.finance import review_budget_aggregates
from sofia.modules.games import review_games
from sofia.modules.household import review_inventory
from sofia.modules.media import review_media

NOW = datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc)


def test_private_domain_receipts_retain_only_snapshot_provenance():
    household = review_inventory({"source_ref":"inventory:owner","observed_at":NOW.isoformat(),"items":[]},now=NOW)
    finance = review_budget_aggregates({"source_ref":"budget:owner","observed_at":NOW.isoformat(),"currency":"USD","period":"2026-11","income_cents":0,"categories":[]},now=NOW)
    calendar = review_schedule_conflicts({"source_ref":"calendar:owner","observed_at":NOW.isoformat(),"events":[]},now=NOW)
    for result in (household,finance,calendar):
        assert result["observed_at"] == NOW.isoformat()
        assert result["effect"] == "none"


def test_media_receipt_retains_timeline_and_rights_basis():
    result=review_media({"source_ref":"media:plan","observed_at":NOW.isoformat(),"items":[
        {"id":"clip:one","start_ms":10,"end_ms":50,"source_duration_ms":40,"licensed":False}]},now=NOW)
    assert result["results"] == [{"id":"clip:one","start_ms":10,"end_ms":50,
        "source_duration_ms":40,"duration_ms":40,"licensed":False,
        "finding":"requires_review","issues":["source_bounds_exceeded","rights_review_missing"],
        "rendered":False}]
    assert not result["action_authorized"]


def test_game_receipt_retains_progress_and_evidence_reference():
    result=review_games({"source_ref":"game:projection","observed_at":NOW.isoformat(),"items":[
        {"id":"objective:one","progress":2,"target":4,"failed":False,
         "evidence_ref":"receipt:opaque"}]},now=NOW)
    item=result["results"][0]
    assert (item["progress"],item["target"],item["evidence_ref"]) == (2,4,"receipt:opaque")
    assert item["completion"] == 0.5 and item["game_state_verified"] is False
    assert result["effect"] == "none" and not result["action_authorized"]
