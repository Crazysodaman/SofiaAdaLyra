"""B03: durable hobbies, interest/hobby decay projections, and fulfillment."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from test.test_life_project_forge import infrastructure

from sofia.core.life import (
    FulfillmentReader, HobbyEngagement, HobbyRecord, HobbyStatus, HobbyStore,
    InterestRecord, InterestStatus, LifeStore, effective_hobby_strength,
    effective_interest_strength, hobby_decay_report, interest_decay_report,
)

pytestmark = [pytest.mark.pkg_core, pytest.mark.pkg_interact]


NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def hobby(name="piano", *, revision=1, audience_id="local:text", status=HobbyStatus.ACTIVE):
    return HobbyRecord(
        f"hobby:{name}", name, f"Playing {name} for its own sake.",
        0.7, 0.9, status, "Chosen from observed leisure evidence.",
        ("evidence:test:1",), audience_id, revision, NOW,
    )


def store(tmp_path):
    path = tmp_path / "sofia.db"
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    bootstrap_canonical_sqlite(path)
    return HobbyStore(path)


def interest(name="codiography", *, recorded_at=NOW, audience_id="local:text"):
    return InterestRecord(
        f"interest:{name}", name, "creative", 0.8, 0.9, InterestStatus.ACTIVE,
        "Source-backed curiosity.", ("evidence:test:1",), audience_id, 1, recorded_at,
    )


def strength_record(recorded_at=NOW):
    return interest(recorded_at=recorded_at)


def engaged(name="piano", *, engaged_at=NOW, minutes=45, audience_id="local:text"):
    return HobbyEngagement(
        f"engagement:{name}:{minutes}", name,
        f"Spent {minutes} minutes with {name} today.", minutes,
        ("evidence:test:2",), audience_id, engaged_at,
    )


def test_hobby_cas_create_and_revise(tmp_path):
    s = store(tmp_path)
    s.hold(hobby(), expected_revision=None)
    assert s.current("piano", audience_id="local:text").revision == 1
    s.hold(hobby(revision=2), expected_revision=1)
    current = s.current("piano", audience_id="local:text")
    assert current.revision == 2 and current.status is HobbyStatus.ACTIVE
    with pytest.raises(RuntimeError):
        s.hold(hobby(revision=2), expected_revision=None)
    assert s.by_id("hobby:piano", audience_id="local:text").revision == 2
    history = s.history("piano", audience_id="local:text")
    assert [item.revision for item in history] == [1, 2]


def test_hobby_reused_id_rejected_between_revisions(tmp_path):
    s = store(tmp_path)
    s.hold(hobby(), expected_revision=None)
    forged = HobbyRecord(
        "hobby:bogus", "piano", "Playing piano.", 0.5, 0.9,
        HobbyStatus.ACTIVE, "Reason.", ("evidence:test:1",),
        "local:text", 2, NOW,
    )
    with pytest.raises(RuntimeError, match="identity changed"):
        s.hold(forged, expected_revision=1)


def test_hobby_active_listing_and_retirement(tmp_path):
    s = store(tmp_path)
    s.hold(hobby(), expected_revision=None)
    s.hold(hobby(name="birdwatching"), expected_revision=None)
    assert [item.name for item in s.active_hobbies(audience_id="local:text")] == [
        "birdwatching", "piano",
    ]
    s.hold(hobby(status=HobbyStatus.RETIRED, revision=2), expected_revision=1)
    remaining = s.active_hobbies(audience_id="local:text")
    assert [item.name for item in remaining] == ["birdwatching"]


def test_engagement_records_list_and_last_time(tmp_path):
    s = store(tmp_path)
    s.hold(hobby(), expected_revision=None)
    s.record_engagement(engaged(), now=NOW + timedelta(minutes=1), hobby_id="hobby:piano")
    later = HobbyEngagement(
        "engagement:2", "piano", "Shorter session.", 30,
        ("evidence:test:2",), "local:text", NOW + timedelta(days=2),
    )
    s.record_engagement(later, now=NOW + timedelta(days=2, minutes=1), hobby_id="hobby:piano")
    rows = s.engagements("piano", audience_id="local:text")
    assert [int(row.duration_minutes) for row in rows] == [30, 45]
    assert s.last_engaged_at("piano", audience_id="local:text") == datetime.fromisoformat(
        (NOW + timedelta(days=2)).astimezone(timezone.utc).isoformat()
    )
    assert s.last_engaged_at("chess", audience_id="local:text") is None
    with pytest.raises(ValueError):
        s.engagements("piano", audience_id="local:text", limit=0)
    with pytest.raises(ValueError):
        s.engagements("piano", audience_id="local:text", limit=257)


def test_engagement_invariants(tmp_path):
    retired = store(tmp_path / "retired")
    retired.hold(hobby(status=HobbyStatus.RETIRED), expected_revision=None)
    with pytest.raises(RuntimeError, match="active hobby"):
        retired.record_engagement(engaged(), now=NOW, hobby_id="hobby:piano")

    s = store(tmp_path / "active")
    s.hold(hobby(), expected_revision=None)
    with pytest.raises(ValueError, match="future"):
        s.record_engagement(engaged(), now=NOW - timedelta(days=1), hobby_id="hobby:piano")
    mismatch = HobbyEngagement(
        "engagement:x", "chess", "Wrong hobby.", 20,
        ("evidence:test:2",), "local:text", NOW,
    )
    with pytest.raises(ValueError, match="does not match"):
        s.record_engagement(mismatch, now=NOW, hobby_id="hobby:piano")
    with pytest.raises(ValueError, match="1..1440"):
        HobbyEngagement(
            "engagement:y", "piano", "Too long.", 1441,
            ("evidence:test:2",), "local:text", NOW,
        )


def test_interest_decay_exact_and_future_grace():
    idle = NOW - timedelta(days=30)
    assert effective_interest_strength(
        strength_record(idle), now=NOW,
    ) == pytest.approx(0.4, abs=1e-6)
    future = interest(recorded_at=NOW + timedelta(days=1))
    assert effective_interest_strength(future, now=NOW) == 0.8
    assert effective_interest_strength(interest(), now=NOW) == 0.8


def test_interest_decay_report_ordering():
    old = interest("old_craft", recorded_at=NOW - timedelta(days=60))
    fresh = interest("fresh_music", recorded_at=NOW)
    equal = interest("equal_music", recorded_at=NOW - timedelta(days=1))
    # two same-day entries: identical effective values → name tiebreak
    older_equal = interest("equal_music", recorded_at=NOW - timedelta(days=1))
    report = interest_decay_report((old, fresh, equal, older_equal), now=NOW)
    ordered = [(item.record.name, item.effective_strength) for item in report[:2]]
    assert ordered[0][0] == "fresh_music" and ordered[0][1] == pytest.approx(0.8)
    assert ordered[1][0] == "equal_music"
    assert report[-1].record.name == "old_craft"
    assert report[-1].days_idle == pytest.approx(60.0)


def test_hobby_decay_reinforces_from_engagement_anchor():
    anchored = HobbyRecord(
        "hobby:chess", "chess", "Daily board practice.", 0.6, 0.8,
        HobbyStatus.ACTIVE, "Chosen.", ("evidence:test:1",),
        "local:text", 1, NOW - timedelta(days=30),
    )
    from_engagement = effective_hobby_strength(
        anchored, now=NOW, last_engaged_at=NOW - timedelta(days=1),
    )
    from_creation = effective_hobby_strength(anchored, now=NOW)
    assert from_engagement == pytest.approx(0.6 * 2 ** (-1 / 45), abs=1e-6)
    assert from_engagement > from_creation > 0
    report = hobby_decay_report(
        (anchored,), now=NOW, last_engaged_by={"chess": NOW - timedelta(days=1)},
    )
    assert report[0].anchored_at == NOW - timedelta(days=1)
    assert report[0].days_idle == pytest.approx(1.0)


def test_fulfillment_reader_aggregates_window(tmp_path):
    path = tmp_path / "sofia.db"
    from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
    bootstrap_canonical_sqlite(path)
    LifeStore(path)  # deploy life schema
    HobbyStore(path)  # deploy hobby schema
    in_window = (NOW - timedelta(days=5)).astimezone(timezone.utc).isoformat()
    out_of_window = (NOW - timedelta(days=200)).astimezone(timezone.utc).isoformat()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            """INSERT INTO life_project VALUES
            ('proj:1','Foxfire','desc','sofia','sofia','local:text',
             'personal_private','interest:codiography','completed','{}',NULL,
             0.5,0.5,?,?,1,NULL)""",
            (in_window, in_window),
        )
        db.execute(
            """INSERT INTO life_project_event VALUES
            (1,'evt:1','proj:1','active','completed','complete','done','[]',
             'sofia',?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_project VALUES
            ('proj:2','Old thing','desc','sofia','sofia','local:text',
             'personal_private','interest:x','completed','{}',NULL,
             0.5,0.5,?,?,1,NULL)""",
            (out_of_window, out_of_window),
        )
        db.execute(
            """INSERT INTO life_project_artifact VALUES
            ('proj:1','artifact:1',1,?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_artifact_evaluation VALUES
            ('eval:1','proj:1','artifact:1',1,'valid','like','{}','kept because good',
             '[]',1,?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_experience VALUES
            ('exp:1',NULL,'artifact_evaluated','Built a radio.','[]',
             'local:text',0,?,?,'{}')""",
            (in_window, in_window),
        )
        db.execute(
            """INSERT INTO life_hobby_engagement VALUES
            ('eng:piano:a','piano','Morning scales.',40,'[]','local:text',?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_hobby_engagement VALUES
            ('eng:piano:b','piano','Afternoon chords.',35,'[]','local:text',?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_interest_revision VALUES
            ('interest:codiography','codiography','creative',0.8,0.9,'active',
             'r','[]','local:text',1,?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_interest_revision VALUES
            ('interest:stamps','stamps','collecting',0.5,0.8,'retired',
             'r','[]','local:text',1,?)""",
            (in_window,),
        )
        db.execute(
            """INSERT INTO life_interest_revision VALUES
            ('interest:old','old','craft',0.9,0.9,'retired','r','[]',
             'local:text',1,?)""",
            (out_of_window,),
        )
    report = FulfillmentReader(path).report(
        now=NOW, audience_id="local:text", window_days=30,
    )
    assert report.projects_completed == 1
    assert report.artifacts_kept == 1
    assert report.experiences_recorded == 1
    assert report.hobby_engagements == 2
    assert report.hobby_minutes == 75
    assert report.engagements_by_hobby == (("piano", 2),)
    assert report.active_interests == 1
    assert report.retired_interests_window == (("stamps", "collecting"),)


def test_coordinator_hobby_and_fulfillment_paths(tmp_path):
    life, _goals, now = infrastructure(tmp_path)
    try:
        evidence = life.record_observation(
            kind="curiosity", source="test:hobby",
            assertion="One observed leisure hour with the piano market.",
            now=now,
        )
        life.record_hobby(
            name="piano", description="Playing the piano purely for leisure.",
            strength=0.7, confidence=0.9, reason="Observed repeated leisure joy.",
            evidence_refs=(evidence,), now=now,
        )
        assert [item.name for item in life.active_hobbies()] == ["piano"]
        life.engage_hobby(
            name="piano", summary="Practiced one scale pattern.",
            duration_minutes=45, evidence_refs=(evidence,),
            engaged_at=now - timedelta(hours=1), now=now,
        )
        assert len(life.hobby_engagements("piano", limit=8)) == 1
        decayed = life.decayed_hobbies(now=now + timedelta(days=1))
        assert decayed[0].record.name == "piano"
        assert decayed[0].anchored_at is not None
        life.retire_hobby(
            name="piano", reason="Lost the taste after review.",
            evidence_refs=(evidence,), now=now + timedelta(days=2),
        )
        assert life.active_hobbies() == ()
        with pytest.raises(RuntimeError):
            life.engage_hobby(
                name="piano", summary="No longer active.",
                duration_minutes=10, evidence_refs=(evidence,), engaged_at=now,
                now=now + timedelta(days=2),
            )
        history = life.hobby_history("piano")
        assert [item.revision for item in history] == [1, 2]
        assert history[1].status is HobbyStatus.RETIRED

        life.revise_interest(
            name="codiography", context="creative", strength=0.9,
            confidence=0.9, reason="Source-backed curiosity.",
            evidence_refs=(evidence,), now=now,
        )
        decayed_interests = life.decayed_interests(
            now=now + timedelta(days=30),
        )
        assert [item.record.name for item in decayed_interests] == ["codiography"]
        assert decayed_interests[0].effective_strength == pytest.approx(0.45)

        life.revise_interest(
            name="stamps", context="collecting", strength=0.4, confidence=0.7,
            reason="Give up stamp collecting after review.",
            evidence_refs=(evidence,), now=now + timedelta(days=2), retire=True,
        )
        report = life.fulfillment_window(
            now=now + timedelta(days=15), window_days=30,
        )
        assert report.engagements_by_hobby == (("piano", 1),)
        assert report.hobby_minutes == 45
        assert report.active_interests == 1
        assert report.retired_interests_window == (("stamps", "collecting"),)
    finally:
        life.close()
