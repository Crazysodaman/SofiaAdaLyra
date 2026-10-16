"""CA-6406: audience-scoped contradictions in the existing PRESENCE source owner.

Only explicit same-event correlations are considered. All results are review
candidates, never autonomous memory facts, authority, permission, or ACT triggers.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
import sqlite3

from sofia.knowledge.observation_conflict import (
    Observation, ObservationSource, compare_observations,
)

MAX_SOURCES = 32
MAX_CONFLICTS = 256


def _source_type(modality: str) -> ObservationSource:
    # An adapter's label is not a verified host/OS attestation.
    return {
        "screen": ObservationSource.SCREEN_CAPTURE,
        "voice": ObservationSource.VOICE_TRANSCRIPT,
        "app": ObservationSource.APP_API,
        "fleet": ObservationSource.APP_API,
    }.get(modality, ObservationSource.MODEL_INFERENCE)


def _scalar_digest(raw_json: str) -> str | None:
    value = json.loads(raw_json)
    if type(value) not in (str, int, bool):
        return None
    if type(value) is str and (not value.strip() or len(value) > 128):
        return None
    return sha256(raw_json.encode("utf-8")).hexdigest()


def _observation(source_id: str, subject: str, predicate: str,
                 value_digest: str, source: ObservationSource,
                 observed_at: datetime, event: str) -> Observation:
    # The decision kernel takes tighter identifiers than existing PRESENCE.
    # Hash all identifiers, never raw values.
    hashed = lambda item: sha256(item.encode("utf-8")).hexdigest()
    return Observation(
        hashed(source_id), hashed(subject), hashed(predicate),
        value_digest, source, observed_at, hashed(event),
    )


def record_correlation(db: sqlite3.Connection, *, observation, receipt,
                       newly_created: bool) -> None:
    event_id = observation.correlation_event_id
    original = db.execute(
        "SELECT event_id FROM presence_observation_correlation WHERE observation_id=?",
        (observation.observation_id,),
    ).fetchone()
    if not newly_created:
        if (None if original is None else original["event_id"]) != event_id:
            raise ValueError("existing observation correlation cannot change")
        return
    if event_id is None:
        return
    if observation.audience_id is None:
        raise PermissionError("correlated observations require an audience")
    if (receipt is None or receipt.original_ref is None
            or receipt.original_access.value != "verified_ref"):
        raise PermissionError("correlation needs original source provenance")

    prior = db.execute(
        """SELECT o.observation_id, o.observed_at, o.value_json, r.modality,
                  r.expires_at
           FROM presence_observation_correlation AS c
           JOIN presence_world_observation AS o
             ON o.observation_id=c.observation_id
           JOIN presence_cross_modal_receipt AS r
             ON r.observation_id=o.observation_id
           WHERE c.event_id=? AND o.subject_id=? AND o.predicate=?
             AND o.audience_id=? AND o.observation_id<>?
           ORDER BY o.observed_at DESC, o.observation_id DESC
           LIMIT ?""",
        (event_id, observation.subject_id, observation.predicate,
         observation.audience_id, observation.observation_id,
         MAX_SOURCES + 1),
    ).fetchall()
    if len(prior) > MAX_SOURCES:
        raise ValueError("event correlation source limit exceeded")
    new_digest = _scalar_digest(
        json.dumps(observation.value, sort_keys=True, ensure_ascii=False)
    )
    if new_digest is not None:
        for earlier in prior:
            if (earlier["expires_at"] is not None and
                    datetime.fromisoformat(earlier["expires_at"]) <=
                    observation.observed_at):
                continue
            prior_digest = _scalar_digest(earlier["value_json"])
            if prior_digest is None:
                continue
            before = _observation(
                earlier["observation_id"], observation.subject_id,
                observation.predicate, prior_digest,
                _source_type(earlier["modality"]),
                datetime.fromisoformat(earlier["observed_at"]), event_id,
            )
            after = _observation(
                observation.observation_id, observation.subject_id,
                observation.predicate, new_digest,
                _source_type(receipt.modality.value),
                observation.observed_at, event_id,
            )
            contradiction = compare_observations(before, after)
            if contradiction is None:
                continue
            first, second = sorted((
                earlier["observation_id"], observation.observation_id
            ))
            key = sha256((first + "\0" + second).encode()).hexdigest()
            db.execute(
                """INSERT OR IGNORE INTO presence_observation_conflict
                   (conflict_id, first_id, second_id, audience_id,
                    kind, review_status, event_id)
                   VALUES(?,?,?,?,?,'pending',?)""",
                (key, first, second, observation.audience_id,
                 contradiction.kind, event_id),
            )
    db.execute(
        "INSERT INTO presence_observation_correlation VALUES(?,?)",
        (observation.observation_id, event_id),
    )
    db.execute(
        """DELETE FROM presence_observation_conflict WHERE conflict_id IN (
             SELECT conflict_id FROM presence_observation_conflict
             ORDER BY rowid DESC LIMIT -1 OFFSET ?
        )""",
        (MAX_CONFLICTS,),
    )


def prune_orphans(db: sqlite3.Connection) -> None:
    db.execute(
        """DELETE FROM presence_observation_conflict
           WHERE first_id NOT IN (SELECT observation_id FROM presence_world_observation)
              OR second_id NOT IN (SELECT observation_id FROM presence_world_observation)"""
    )
    db.execute(
        """DELETE FROM presence_observation_correlation
           WHERE observation_id NOT IN (SELECT observation_id FROM presence_world_observation)"""
    )


def scoped_conflicts(db: sqlite3.Connection, *, audience_id: str, limit: int = 20
                     ) -> tuple[dict, ...]:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("review limit must be 1..50")
    rows = db.execute(
        """SELECT conflict_id,first_id,second_id,kind,review_status,event_id
           FROM presence_observation_conflict WHERE audience_id=?
           ORDER BY rowid DESC LIMIT ?""",
        (audience_id,limit),
    ).fetchall()
    return tuple({
        "conflict_id": row["conflict_id"],
        "first_source_ref": row["first_id"],
        "second_source_ref": row["second_id"],
        "kind": row["kind"],
        "status": row["review_status"],
        "event_id": row["event_id"],
        "requires_authorized_review": True,
        "factual_resolution": None,
    } for row in rows)
