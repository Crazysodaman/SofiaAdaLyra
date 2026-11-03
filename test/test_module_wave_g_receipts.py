"""Wave G proposals retain scoped evidence while keeping effects disabled."""
from datetime import datetime, timezone

from sofia.modules.desktop_automation import review_desktop_automation
from sofia.modules.remote_access.analysis import assess_session
from sofia.modules.trains import review_trains
from sofia.modules.vision.projection_review import review_vision

NOW=datetime(2026,11,3,5,0,tzinfo=timezone.utc)


def test_vision_retains_consent_and_bounded_detection_metadata():
    result=review_vision({"source_ref":"vision:projection","observed_at":NOW.isoformat(),"items":[
        {"id":"detection:one","class":"person","confidence":0.8,"x":0.1,"y":0.2,
         "width":0.3,"height":0.4,"consent_ref":"permit:one"}]},now=NOW)
    item=result["results"][0]
    assert item["consent_ref"] == "permit:one"
    assert item["bounds"] == {"x":0.1,"y":0.2,"width":0.3,"height":0.4}
    assert item["verified_visual_fact"] is False and result["effect"] == "none"


def test_desktop_plan_retains_denial_inputs_without_authorizing_action():
    result=review_desktop_automation({"source_ref":"desktop:proposal","observed_at":NOW.isoformat(),"items":[
        {"id":"action:one","operation":"click","target_ref":"window:one",
         "approval_ref":"approval:reported","stop_clear":False,
         "gaming_status":"gaming"}]},now=NOW)
    item=result["results"][0]
    assert item["approval_ref"] == "approval:reported" and item["stop_clear"] is False
    assert item["gaming_status"] == "gaming" and item["authorized"] is False


def test_train_plan_retains_simulation_basis_without_live_clearance():
    result=review_trains({"source_ref":"jmri:supplied","observed_at":NOW.isoformat(),"items":[
        {"id":"route:one","blocks":["block:a"],"occupied_blocks":["block:a"],
         "turnouts_aligned":False,"power_state":"unknown"}]},now=NOW)
    item=result["results"][0]
    assert item["occupied_blocks"] == ["block:a"] and item["power_state"] == "unknown"
    assert item["live_route_clearance_verified"] is False and result["effect"] == "none"


def test_remote_access_retains_sanitized_report_basis_without_authority():
    result=assess_session({"source_ref":"access:probe","session_ref":"session:one",
        "observed_at":NOW.isoformat(),"transport":"ssh","status":"active",
        "mfa_reported":False,"device_enrolled_reported":True,
        "channel_encrypted_reported":True,"idle_seconds":1000,
        "revoke_reported":False},now=NOW)
    assert result["reported_status"] == "active" and result["mfa_reported"] is False
    assert result["idle_seconds"] == 1000
    assert result["authorization_conclusion"] == "not_evaluated" and result["effect"] == "none"
