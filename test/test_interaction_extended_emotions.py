"""Extended labels are appraisals, never proof of feeling or permission."""
from datetime import datetime, timezone

import pytest

from sofia.interaction.registry import EMOTION_EXTENSIONS
from sofia.personality.emotion import EMOTIONS, EmotionalJournal

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_extended_labels_are_active_but_never_auto_recorded(tmp_path):
    journal = EmotionalJournal(tmp_path / 'isolated.db')
    assert EMOTION_EXTENSIONS <= EMOTIONS
    assert journal.recent(now=NOW) == ()
    journal.record(
        source='inferred', evidence_ref='saved-1', event_id='app-1',
        description='A provisional, fictional appraisal.',
        emotions=('embarrassment', 'affection'), occurred_at=NOW,
    )
    journal.revise(
        event_id='app-1', emotions=('aversion', 'uncertainty'),
        reason='Later source-linked context changes the fictional appraisal.',
        revised_at=NOW,
    )
    event = journal.recent(now=NOW)[0]
    assert event.original_emotions == ('embarrassment', 'affection')
    assert event.current_emotions == ('aversion', 'uncertainty')
    assert event.revision_count == 1


def test_unknown_duplicate_or_overlong_appraisals_rejected(tmp_path):
    journal = EmotionalJournal(tmp_path / 'isolated.db')
    for invalid in (('imaginary-label',), ('anger', 'anger'), ('anger',) * 7):
        with pytest.raises(ValueError):
            journal.record(source='inferred', evidence_ref='saved-2',
                           description='A test appraisal.', emotions=invalid,
                           occurred_at=NOW)
