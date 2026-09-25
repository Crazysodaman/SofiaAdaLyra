"""No active worker, no notifications and no production DB in these tests."""
from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.interaction.goal_journal import GoalJournal

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


@pytest.fixture
def goals(tmp_path):
    db = tmp_path / 'state.db'
    with sqlite3.connect(db) as cx:
        cx.execute('CREATE TABLE conversation_messages (id TEXT PRIMARY KEY, role TEXT)')
        cx.execute("INSERT INTO conversation_messages VALUES ('saved','user')")
        cx.execute("INSERT INTO conversation_messages VALUES ('assistant-message','assistant')")
    return GoalJournal(db)


def test_goal_selection_requires_explicit_enable_and_idle(goals):
    goals.create_goal(goal_id='g1', source_id='saved',
                      title='Review Gaia plans', kind='lab_suggestion', priority=3, at=NOW)
    assert goals.next_goal(enabled=True, user_idle=True) is None
    goal = goals.transition(goal_id='g1', transition_id='t1', source_id='saved',
                            expected_status='proposed', next_status='active', at=NOW)
    assert goals.next_goal(enabled=False, user_idle=True) is None
    assert goals.next_goal(enabled=True, user_idle=False) is None
    assert goals.next_goal(enabled=True, user_idle=True) == goal


def test_unknown_presence_is_not_absence_and_queue_never_means_delivered(goals):
    goals.create_goal(goal_id='g1', source_id='saved',
                      title='Review Gaia plans', kind='lab_suggestion', priority=3, at=NOW)
    goals.transition(goal_id='g1', transition_id='t1', source_id='saved',
                     expected_status='proposed', next_status='active', at=NOW)
    opts = dict(message_id='m1', goal_id='g1', evidence_id='assistant-message',
                content='Want to review our recorded Gaia plan?',
                at=NOW, opted_in=True, mode='queue_only')
    assert goals.queue_message(**opts, presence='unknown') is None
    assert goals.queue_message(**opts, presence='present') is None
    assert goals.pending() == ()
    message = goals.queue_message(**opts, presence='away')
    assert message.status == 'queued' and goals.pending() == (message,)
    assert goals.queue_message(**opts, presence='away') == message
    assert goals.queue_message(**{**opts, 'message_id': 'm2'}, presence='away') is None
    goals.cancel_message('m1')
    assert goals.pending() == ()


def test_missing_source_and_unapproved_delivery_are_rejected(goals):
    with pytest.raises(ValueError):
        goals.create_goal(goal_id='bad', source_id='invented',
                          title='X', kind='review', priority=1, at=NOW)
    goals.create_goal(goal_id='g1', source_id='saved',
                      title='Review Gaia plans', kind='review', priority=1, at=NOW)
    goals.transition(goal_id='g1', transition_id='t1', source_id='saved',
                     expected_status='proposed', next_status='active', at=NOW)
    opts = dict(message_id='m1', goal_id='g1', evidence_id='saved',
                content='test', at=NOW, presence='away')
    assert goals.queue_message(**opts, opted_in=False, mode='queue_only') is None
    with pytest.raises(ValueError):
        goals.queue_message(**opts, opted_in=True, mode='notify')
