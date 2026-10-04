from datetime import datetime, timezone
import sqlite3

import pytest

from sofia.act.history import delivery_history


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def test_missing_delivery_tables_produce_empty_history():
    with sqlite3.connect(":memory:") as db:
        history = delivery_history(db, recipient_id="sparks", channel="text", destination="local", now=NOW)
    assert history.delivered_today == 0
    assert history.delivered_candidate_ids == frozenset()
    assert history.last_delivered_at is None


@pytest.mark.parametrize("legacy", [False, True])
def test_shared_history_counts_both_queues_and_isolates_destination(legacy):
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE act_delivery_attempts(attempt_id, message_id, recipient_id, channel, destination, status, finished_at)")
        db.execute("INSERT INTO act_delivery_attempts VALUES(1,'message','sparks','text','local','delivered',?)", (NOW.isoformat(),))
        db.execute("INSERT INTO act_delivery_attempts VALUES(2,'failed','sparks','text','local','failed',?)", (NOW.isoformat(),))
        db.execute("INSERT INTO act_delivery_attempts VALUES(3,'other','sparks','text','remote','delivered',?)", (NOW.isoformat(),))
        category_column = "" if legacy else ",category"
        db.execute("CREATE TABLE act_system_notice(notice_id,recipient_id,channel,destination,status,finished_at" + category_column + ")")
        for name, category in (("social-notice", "social"), ("operational-notice", "operational")):
            row = (name, "sparks", "text", "local", "delivered", NOW.isoformat())
            if not legacy:
                row += (category,)
            db.execute("INSERT INTO act_system_notice VALUES(" + ",".join("?" for _ in row) + ")", row)
        history = delivery_history(db, recipient_id="sparks", channel="text", destination="local", now=NOW)
    assert history.delivered_candidate_ids == frozenset({"message", "social-notice", "operational-notice"})
    assert history.delivered_today == 3
    assert history.social_delivered_today == (1 if legacy else 2)
    assert history.operational_delivered_today == (2 if legacy else 1)
    assert history.last_delivered_at == NOW
