"""Wave C module receipts preserve validated evidence without adding effects."""
from datetime import datetime, timezone

from sofia.modules.creative_studio import review_creative_studio
from sofia.modules.development import review_development
from sofia.modules.file_watch import summarize_changes
from sofia.modules.project_forge import review_artifact_manifest

NOW = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def test_development_receipt_preserves_review_evidence():
    result = review_development({
        "source_ref": "review:patch", "observed_at": NOW.isoformat(),
        "items": [{"id": "change:1", "path": "src/sofia/modules/example.py",
                   "operation": "modify", "tests_passed": True,
                   "reviewed": True, "protected": False}],
    }, now=NOW)
    assert result["results"] == [{
        "id": "change:1", "path": "src/sofia/modules/example.py",
        "operation": "modify", "tests_passed": True, "reviewed": True,
        "protected": False, "finding": "review_eligible", "reasons": [],
    }]
    assert result["effect"] == "none" and not result["action_authorized"]


def test_creative_receipt_preserves_asset_digest_and_review():
    result = review_creative_studio({
        "source_ref": "storyboard:one", "observed_at": NOW.isoformat(),
        "items": [{"id": "scene:1", "start_s": 0, "end_s": 2,
                   "asset_digest": DIGEST, "asset_reviewed": True}],
    }, now=NOW)
    assert result["results"][0]["asset_digest"] == DIGEST
    assert result["results"][0]["asset_reviewed"] is True
    assert result["effect"] == "none" and not result["action_authorized"]


def test_forge_receipt_preserves_timestamp_and_criterion_identity():
    result = review_artifact_manifest({
        "source_ref": "forge:manifest", "observed_at": NOW.isoformat(),
        "project_ref": "project:one",
        "artifacts": [{"artifact_id": "artifact:one", "digest_sha256": DIGEST,
                       "reviewed": True, "test_result": "passed"}],
        "criteria": [{"criterion_id": "criterion:one",
                      "artifact_id": "artifact:one", "met": True}],
    }, now=NOW)
    assert result["observed_at"] == NOW.isoformat()
    assert result["artifacts"][0]["criteria"] == [
        {"criterion_id": "criterion:one", "met": True}]
    assert result["all_acceptance_verified"] is False


def test_file_watch_receipt_preserves_feed_timestamp_while_redacting_path():
    result = summarize_changes({
        "source_ref": "watch:feed", "root_ref": "root:approved",
        "observed_at": NOW.isoformat(),
        "events": [{"path": "project/.env", "kind": "modified",
                    "is_directory": False}],
    }, now=NOW)
    assert result["observed_at"] == NOW.isoformat()
    assert result["visible_events"] == []
    assert result["redacted_sensitive_count"] == 1
    assert ".env" not in str(result)
