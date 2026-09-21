from datetime import datetime, timezone

import pytest

from sofia.package_foundations.core import StartupEvidence


def test_grouped_observations_do_not_infer_shutdown_or_cause():
    evidence = StartupEvidence(datetime.now(timezone.utc), True, ('a', 'a', 'b'))
    assert evidence.public_summary() == ('A previous runtime was observed. '
                                         '2 distinct workspace path(s) changed.')
    assert 'shutdown' not in evidence.public_summary()
    assert 'a' not in evidence.public_summary().split('changed.')[0]


def test_missing_evidence_is_not_reported_as_a_restart():
    assert 'No previous runtime evidence' in StartupEvidence(
        datetime.now(timezone.utc), False).public_summary()


def test_naive_time_rejected():
    with pytest.raises(ValueError):
        StartupEvidence(datetime(2026, 1, 1), True)
