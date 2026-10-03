from datetime import datetime, timedelta, timezone

from sofia.ops.recovery import (
    BackupEvidence,
    DEFAULT_RECOVERY_OBJECTIVES,
    RecoveryObjectives,
)


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def backup_at(moment: datetime) -> BackupEvidence:
    return BackupEvidence(
        backup_id="backup-1",
        source_host_id="venus",
        failure_domain="external",
        created_at=moment,
        content_digest="a" * 64,
    )


def test_default_recovery_objectives_are_explicit():
    assert DEFAULT_RECOVERY_OBJECTIVES.rpo_seconds == 3600
    assert DEFAULT_RECOVERY_OBJECTIVES.rto_seconds == 1800


def test_backup_age_is_measured_against_rpo():
    objectives = RecoveryObjectives(
        rpo_seconds=3600,
        rto_seconds=1800,
    )

    assert objectives.backup_within_rpo(
        backup_at(NOW - timedelta(minutes=59)),
        now=NOW,
    )
    assert not objectives.backup_within_rpo(
        backup_at(NOW - timedelta(minutes=61)),
        now=NOW,
    )


def test_restore_duration_is_measured_against_rto():
    objectives = RecoveryObjectives(
        rpo_seconds=3600,
        rto_seconds=1800,
    )

    assert objectives.restore_within_rto(
        started_at=NOW,
        verified_at=NOW + timedelta(minutes=29),
    )
    assert not objectives.restore_within_rto(
        started_at=NOW,
        verified_at=NOW + timedelta(minutes=31),
    )
