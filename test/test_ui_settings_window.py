"""Exercise real Tk widgets under a display, plus headless mood projection."""
from datetime import datetime, timezone
import os

import pytest

from sofia.config.user_settings import RuntimeUserSettingsStore
from sofia.emotion.journal import EmotionalJournal
from sofia.social.model import SocialScope
from sofia.social.principals import SPARKS_PRINCIPAL_ID
from sofia.ui.wardrobe_panel import current_mood


def test_mood_shows_owner_emotion_and_time_without_other_principal_data(tmp_path):
    state = tmp_path / "sofia.db"
    journal = EmotionalJournal(state)
    now = datetime.now(timezone.utc)
    for principal, emotion, evidence in ((SPARKS_PRINCIPAL_ID, "joy", "owner-observation"), ("person:other", "anger", "private-other-observation")):
        journal.record(source="observed", evidence_ref=evidence, description="Test emotional appraisal", emotions=(emotion,), occurred_at=now, subject=principal, scope=SocialScope.relationship(principal))
    text = current_mood(state)
    assert "joy:" in text and "% intensity" in text
    assert now.isoformat() in text
    assert "owner-observation" in text
    assert "anger" not in text and "private-other-observation" not in text


@pytest.mark.skipif(not os.environ.get("DISPLAY") and os.name != "nt", reason="Real Tk requires a display")
def test_real_settings_save_reopen_and_wardrobe_submission(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import messagebox
    from sofia.ui import settings_window
    from sofia.avatar.wardrobe_review import WardrobeReviewStore
    from sofia.ui.control_center import DesktopControlSettingsStore, MASTER_SETTINGS_SECTIONS
    path = tmp_path / "custom-selected.db"
    original_root = tk.Tk
    captured = []
    original_sections = settings_window.SettingsSections
    class CaptureSections(original_sections):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured.append(self)
    monkeypatch.setattr(settings_window, "SettingsSections", CaptureSections)
    def fail(title, message, **kwargs):
        pytest.fail(f"{title}: {message}")
    monkeypatch.setattr(messagebox, "showerror", fail)
    def widgets(parent):
        for child in parent.winfo_children():
            yield child
            yield from widgets(child)
    for restart in (False, True):
        root = original_root()
        monkeypatch.setattr(tk, "Tk", lambda: root)
        def interact():
            root.update_idletasks()
            extra = captured[-1]
            navigation = next(w for w in widgets(root) if w.winfo_class() == "Listbox")
            assert navigation.size() == len(MASTER_SETTINGS_SECTIONS)
            assert "Permissions" in MASTER_SETTINGS_SECTIONS
            if restart:
                assert extra.variables["adaptive_theme"].get() is False
                assert extra.variables["avatar_routines_enabled"].get() is False
                assert extra.groups["outreach"][1]["mute"].get() is True
                assert not DesktopControlSettingsStore(path).load().close_to_tray
                assert WardrobeReviewStore(path).list()[0]["status"] == "pending"
            else:
                extra.variables["adaptive_theme"].set(False)
                extra.variables["avatar_routines_enabled"].set(False)
                extra.groups["outreach"][1]["mute"].set(True)
                extra.wardrobe.new("garment")
                extra.wardrobe.entries[("name",)][0].set("Owner-authored garment")
                extra.wardrobe.submit()
                close = next(w for w in widgets(root) if w.winfo_class() == "TCheckbutton" and w.cget("text") == "Keep the tray running when chat closes")
                close.invoke()
                save = next(w for w in widgets(root) if w.winfo_class() == "TButton" and w.cget("text") == "Save")
                save.invoke()
                assert not RuntimeUserSettingsStore(path).load().adaptive_theme
            root.destroy()
        root.mainloop = interact
        assert settings_window.run_settings_window(state_path=path, section="Wardrobe") == 0
