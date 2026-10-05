from dataclasses import replace
from datetime import datetime, timezone

from test.test_ui_application import configuration
from sofia.application import SofiaApplication
from sofia.avatar.wardrobe_review import WardrobeReviewStore, document
from sofia.cognition.model import CognitiveResponse
from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore


def test_editor_review_updates_live_avatar_and_survives_application_restart(configuration, monkeypatch):
    preferences = RuntimeUserSettingsStore(configuration.state_path)
    preferences.save(RuntimeUserSettings(avatar_routines_enabled=False, habit_learning_enabled=False, idle_reflections_enabled=False))
    application = SofiaApplication(configuration)
    application.start()
    try:
        store = WardrobeReviewStore(configuration.state_path)
        raw = document(next(bp.design for bp in store.catalog().blueprints if not bp.private_only))
        raw.update(item_id="custom.editor.runtime", name="Owner-designed runtime garment")
        before = application.runtime.avatar_presentation.current
        def approve(request, **kwargs):
            assert request.allow_tools is False
            return CognitiveResponse(content='{"decision":"accept","reason":"I want this design in my wardrobe."}')
        monkeypatch.setattr(application.runtime, "respond", approve)
        key = store.submit("garment", raw)
        assert application.background_coordinator._tasks["wardrobe_review"](datetime.now(timezone.utc)) == key
        assert store.list()[0]["status"] == "approved"
        assert any(bp.garment.item_id == raw["item_id"] for bp in application._presentation_bundle.catalog.blueprints)
        assert application.runtime.avatar_presentation.current == before
    finally:
        application.shutdown()
    restarted = SofiaApplication(configuration)
    restarted.start()
    try:
        assert any(bp.garment.item_id == raw["item_id"] for bp in restarted._presentation_bundle.catalog.blueprints)
        assert restarted.runtime.avatar_presentation.current == before
        assert restarted._avatar_routines_enabled is False
    finally:
        restarted.shutdown()
