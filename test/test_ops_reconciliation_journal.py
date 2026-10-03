from datetime import datetime, timedelta, timezone

from sofia.ops.desired import Drift
from sofia.ops.reconciliation_journal import FleetReconciliationJournal
from sofia.ops.repair_plan import FleetRepairPlanner


NOW = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)


def proposal():
    return FleetRepairPlanner().propose(
        Drift(
            "workload_placement",
            "plex",
            "artemis",
            "venus",
        )
    )


def test_reconciliation_journal_dedupes_same_active_drift(tmp_path):
    journal = FleetReconciliationJournal(tmp_path / "sofia.db")
    item = proposal()

    first = journal.observe((item,), now=NOW)
    second = journal.observe(
        (item,),
        now=NOW + timedelta(minutes=15),
    )

    assert len(first) == 1
    assert second == ()
    active = journal.active()
    assert len(active) == 1
    assert active[0].proposal_key == first[0].proposal_key
    assert active[0].first_seen == NOW
    assert active[0].last_seen == NOW + timedelta(minutes=15)
    assert active[0].active is True


def test_reconciliation_journal_marks_disappeared_drift_resolved(tmp_path):
    journal = FleetReconciliationJournal(tmp_path / "sofia.db")
    first = journal.observe((proposal(),), now=NOW)[0]

    created = journal.observe(
        (),
        now=NOW + timedelta(minutes=15),
    )

    assert created == ()
    assert journal.active() == ()
    stored = journal.get(first.proposal_key)
    assert stored is not None
    assert stored.active is False
    assert stored.last_seen == NOW + timedelta(minutes=15)
