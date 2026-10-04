"""Shared read-only delivery history projection for both ACT queues."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from .outreach import History


def delivery_history(
    db: sqlite3.Connection,
    *,
    recipient_id: str,
    channel: str,
    destination: str,
    now: datetime,
) -> History:
    social_rows = []
    attempts_table = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='act_delivery_attempts'"
    ).fetchone()
    if attempts_table is not None:
        social_rows = db.execute(
            """
            SELECT message_id, finished_at
            FROM act_delivery_attempts
            WHERE recipient_id=? AND channel=? AND destination=?
              AND status='delivered'
            ORDER BY finished_at, attempt_id
            """,
            (recipient_id, channel, destination),
        ).fetchall()
    social_times = [
        datetime.fromisoformat(row[1]).astimezone(timezone.utc)
        for row in social_rows
        if row[1] is not None
    ]

    social_notice_rows = []
    operational_rows = []
    notice_table = db.execute(
        "SELECT 1 FROM sqlite_master "
        "WHERE type='table' AND name='act_system_notice'"
    ).fetchone()
    if notice_table is not None:
        columns = {
            row[1]
            for row in db.execute(
                "PRAGMA table_info(act_system_notice)"
            )
        }
        if "category" in columns:
            notice_rows = db.execute(
                """
                SELECT notice_id, finished_at, category
                FROM act_system_notice
                WHERE recipient_id=? AND channel=? AND destination=?
                  AND status='delivered'
                ORDER BY finished_at, notice_id
                """,
                (recipient_id, channel, destination),
            ).fetchall()
            social_notice_rows = [
                row for row in notice_rows
                if row[2] == "social"
            ]
            operational_rows = [
                row for row in notice_rows
                if row[2] == "operational"
            ]
        else:
            operational_rows = db.execute(
                """
                SELECT notice_id, finished_at
                FROM act_system_notice
                WHERE recipient_id=? AND channel=? AND destination=?
                  AND status='delivered'
                ORDER BY finished_at, notice_id
                """,
                (recipient_id, channel, destination),
            ).fetchall()
    social_notice_times = [
        datetime.fromisoformat(row[1]).astimezone(timezone.utc)
        for row in social_notice_rows
        if row[1] is not None
    ]
    operational_times = [
        datetime.fromisoformat(row[1]).astimezone(timezone.utc)
        for row in operational_rows
        if row[1] is not None
    ]
    social_times = sorted(social_times + social_notice_times)

    all_times = sorted(social_times + operational_times)
    ids = frozenset(
        [row[0] for row in social_rows]
        + [row[0] for row in social_notice_rows]
        + [row[0] for row in operational_rows]
    )
    day = now.date().isoformat()

    def today_count(values):
        return sum(
            1 for value in values
            if value.date().isoformat() == day
        )

    return History(
        delivered_candidate_ids=ids,
        last_delivered_at=all_times[-1] if all_times else None,
        delivered_today=today_count(all_times),
        delivered_day_utc=day if all_times else None,
        social_last_delivered_at=(
            social_times[-1] if social_times else None
        ),
        social_delivered_today=today_count(social_times),
        operational_last_delivered_at=(
            operational_times[-1] if operational_times else None
        ),
        operational_delivered_today=today_count(operational_times),
    )
