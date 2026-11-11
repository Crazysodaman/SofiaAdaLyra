"""Shared Python/Rust Fleet admission wire contract regressions."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sofia.sdk.fleet_admission import (
    FLEET_ADMISSION_SCHEMA,
    UntrustedFleetAdmissionRequest,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts" / "platform" / "fleet-admission-valid-v1.json"
NOW = datetime(2026, 11, 11, 12, 0, 20, tzinfo=timezone.utc)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_fixture_matches_rust_acceptance():
    request = UntrustedFleetAdmissionRequest.parse(FIXTURE.read_bytes(), now=NOW)
    assert request.schema == FLEET_ADMISSION_SCHEMA
    assert request.candidate_host_id == "worker"
    assert request.initial_permission_level == 2
    assert request.to_payload() == _payload()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operation", "fleet.decommission"),
        ("operation", "fleet.enroll"),
        ("initial_permission_level", 4),
        ("requested_role", "system"),
        ("candidate_node_id", "not-a-node"),
        ("candidate_public_key_sha256", "A" * 64),
        ("policy_revision", 0),
    ],
)
def test_unsafe_or_unreviewed_admission_is_rejected(field, value):
    payload = _payload()
    payload[field] = value
    with pytest.raises((ValueError, PermissionError)):
        UntrustedFleetAdmissionRequest.from_payload(payload, now=NOW)


def test_owner_secret_or_extra_fields_never_enter_the_contract():
    payload = _payload()
    payload["owner_secret"] = "ab" * 32
    with pytest.raises(ValueError):
        UntrustedFleetAdmissionRequest.from_payload(payload, now=NOW)


def test_duplicate_keys_and_unbounded_windows_are_rejected():
    raw = b'{"schema":"x","schema":"y"}'
    with pytest.raises(ValueError):
        UntrustedFleetAdmissionRequest.parse(raw, now=NOW)
    for now in (
        datetime(2026, 11, 11, 12, 5, tzinfo=timezone.utc),
        datetime(2026, 11, 11, 11, 59, tzinfo=timezone.utc),
    ):
        with pytest.raises(PermissionError):
            UntrustedFleetAdmissionRequest.parse(FIXTURE.read_bytes(), now=now)
