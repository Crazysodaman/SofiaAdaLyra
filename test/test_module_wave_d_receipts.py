"""Wave D module-local avatar reviews preserve their validated evidence."""
from datetime import datetime, timezone

from sofia.modules.avatar3d import review_avatar3d
from sofia.modules.avatar_studio import review_avatar_studio

NOW = datetime(2026, 11, 3, 3, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def test_avatar3d_receipt_retains_rig_and_joint_constraint_basis():
    result = review_avatar3d({
        "source_ref":"rig:proposal", "observed_at":NOW.isoformat(),
        "items":[{"id":"pose:head","joint":"head","angle_deg":75,
                  "minimum_deg":-60,"maximum_deg":60,"rig_digest":DIGEST}],
    }, now=NOW)
    assert result["results"] == [{
        "id":"pose:head","joint":"head","angle_deg":75.0,
        "minimum_deg":-60.0,"maximum_deg":60.0,"rig_digest":DIGEST,
        "finding":"limit_exceeded","pose_rendered":False,
    }]
    assert result["effect"] == "none" and not result["action_authorized"]


def test_avatar_studio_receipt_retains_private_review_basis():
    result = review_avatar_studio({
        "source_ref":"assets:proposal", "observed_at":NOW.isoformat(),
        "items":[{"id":"layer:eyes","slot":"eyes","layer_order":10,
                  "content_class":"private","reviewed":True,
                  "alpha_present":True}],
    }, now=NOW)
    assert result["results"] == [{
        "id":"layer:eyes","slot":"eyes","layer_order":10,
        "content_class":"private","reviewed":True,"alpha_present":True,
        "finding":"requires_review",
        "issues":["private_distribution_review_required"],
        "wardrobe_modified":False,
    }]
    assert result["effect"] == "none" and not result["action_authorized"]
