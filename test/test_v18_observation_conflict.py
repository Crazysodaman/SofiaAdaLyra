from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.knowledge.observation_conflict import (
    ConflictError,
    Observation,
    ObservationSource,
    compare_observations,
)

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def test_agreeing_observations_produce_no_contradiction():
    a = Observation("o1", "host:venus", "service.llm", "running",
                    ObservationSource.HOST_RECEIPT, NOW)
    b = Observation("o2", "host:venus", "service.llm", "running",
                    ObservationSource.SCREEN_CAPTURE, NOW)
    assert compare_observations(a, b) is None


def test_different_subjects_are_unrelated_observations():
    a = Observation("o1", "host:venus", "service.llm", "running",
                    ObservationSource.HOST_RECEIPT, NOW)
    b = Observation("o2", "host:artemis", "service.llm", "stopped",
                    ObservationSource.HOST_RECEIPT, NOW)
    assert compare_observations(a, b) is None


def test_authoritative_receipt_outranks_screen_but_disagreement_is_preserved():
    host = Observation("o1", "host:venus", "service.llm", "running",
                       ObservationSource.HOST_RECEIPT, NOW)
    screen = Observation("o2", "host:venus", "service.llm", "stopped",
                         ObservationSource.SCREEN_CAPTURE, NOW)
    conflict = compare_observations(screen, host)
    assert conflict is not None
    assert conflict.kind == "value_conflict"
    assert conflict.preferred_source is ObservationSource.HOST_RECEIPT
    assert conflict.requires_verification is False
    assert conflict.first is screen and conflict.second is host


def test_two_weak_sources_require_authorized_verification():
    voice = Observation("o1", "user:owner", "preference.tea", "green",
                        ObservationSource.VOICE_TRANSCRIPT, NOW)
    screen = Observation("o2", "user:owner", "preference.tea", "black",
                         ObservationSource.SCREEN_CAPTURE, NOW)
    conflict = compare_observations(voice, screen)
    assert conflict is not None
    assert conflict.requires_verification is True
    assert conflict.preferred_source is None


def test_clock_skew_is_reported_as_time_disagreement_not_value_change():
    device = Observation("o1", "host:venus", "service.llm", "running",
                         ObservationSource.DEVICE_CLOCK, NOW)
    remote = Observation("o2", "host:venus", "service.llm", "running",
                         ObservationSource.HOST_RECEIPT, NOW + timedelta(hours=2))
    conflict = compare_observations(device, remote)
    # Same value: no contradiction at all, even across a clock gap.
    assert conflict is None


def test_contradiction_rejects_malformed_observations():
    with pytest.raises(ConflictError):
        Observation("o1", "host:venus", "service.llm", " ", 
                    ObservationSource.HOST_RECEIPT, NOW)
    with pytest.raises(ConflictError):
        Observation("o1", "host:venus", "service.llm", "running",
                    ObservationSource.HOST_RECEIPT, datetime(2026, 1, 1))
    with pytest.raises(TypeError):
        Observation("o1", "host:venus", "service.llm", "running", "host", NOW)
