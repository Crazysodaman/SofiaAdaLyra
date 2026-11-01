"""G5 recovery evidence may never certify an unverified or newer backup."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.ops.recovery import (
    BackupEvidence, RecoveryDenied, RecoveryGuard, RestoreVerification,
)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


def _evidence(*, verified_at=None, success=True):
    backup = BackupEvidence(
        backup_id="backup:protected:1", source_host_id="venus",
        failure_domain="home-lab", created_at=NOW,
        content_digest="a" * 64,
    )
    restore = RestoreVerification(
        backup_id=backup.backup_id,
        verified_at=verified_at or NOW + timedelta(minutes=1),
        verifier="independent:restore-inspector",
        succeeded=success,
    )
    return backup, restore


def test_g5_current_cross_failure_domain_restore_is_eligible():
    backup, restore = _evidence()
    RecoveryGuard().require(
        backup, restore, target_failure_domain="offsite",
    )


def test_g5_old_restore_cannot_verify_newer_backup():
    backup, restore = _evidence(
        verified_at=NOW - timedelta(seconds=1),
    )
    with pytest.raises(RecoveryDenied, match="predates"):
        RecoveryGuard().require(
            backup, restore, target_failure_domain="offsite",
        )


def test_g5_recovery_denies_same_failure_domain_and_failed_restore():
    backup, restore = _evidence()
    with pytest.raises(RecoveryDenied, match="not isolated"):
        RecoveryGuard().require(
            backup, restore, target_failure_domain="home-lab",
        )
    _, failed = _evidence(success=False)
    with pytest.raises(RecoveryDenied, match="independent restore"):
        RecoveryGuard().require(
            backup, failed, target_failure_domain="offsite",
        )


@pytest.mark.parametrize("target", ["", " ", None])
def test_g5_recovery_refuses_missing_target_failure_domain(target):
    backup, restore = _evidence()
    with pytest.raises(ValueError, match="target failure domain"):
        RecoveryGuard().require(
            backup, restore, target_failure_domain=target,
        )
