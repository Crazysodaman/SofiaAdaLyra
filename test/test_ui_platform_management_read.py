"""Shared read-only management contract is syntax, never authentication."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sofia.sdk.platform_management import (
    MANAGEMENT_READ_SCHEMA, UntrustedManagementRead,
)

pytestmark = pytest.mark.pkg_ui

FIXTURE = (Path(__file__).resolve().parents[1] / "contracts" /
           "platform" / "management-read-valid-v1.json")
NOW = datetime(2026, 11, 8, 4, tzinfo=timezone.utc)


def test_valid_fixture_matches_rust_schema_and_remains_untrusted():
    raw = FIXTURE.read_bytes()
    request = UntrustedManagementRead.parse(raw, now=NOW)
    assert request.schema == MANAGEMENT_READ_SCHEMA
    assert request.operation == "platform.status"
    assert request.expected_generation == 3
    assert request.to_payload() == json.loads(raw)


@pytest.mark.parametrize("operation", [
    "module.remove", "module.activate", "core.start", "platform.install",
    "safe.approve", "settings.write",
])
def test_mutating_operations_never_admitted(operation):
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original["operation"] = operation
    with pytest.raises(PermissionError, match="read-only"):
        UntrustedManagementRead.from_payload(original, now=NOW)


def test_duplicate_keys_unknown_fields_and_forged_grants_denied():
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original["owner_grant"] = "self-approved"
    with pytest.raises(ValueError, match="unreviewed"):
        UntrustedManagementRead.from_payload(original, now=NOW)
    duplicate = b'{"schema":"x","schema":"y"}'
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementRead.parse(duplicate, now=NOW)


@pytest.mark.parametrize("changed", [
    {"expected_generation": 0},
    {"expected_generation": True},
    {"target_platform_id": "../bad"},
    {"deadline": "2026-11-08T03:59:59Z"},
    {"created_at": "2026-11-08T03:50:00Z"},
    {"protocol": "2.0"},
])
def test_generation_identity_and_time_fences(changed):
    original = json.loads(FIXTURE.read_text(encoding="utf-8"))
    original.update(changed)
    with pytest.raises((ValueError, PermissionError)):
        UntrustedManagementRead.from_payload(original, now=NOW)


def test_bounded_input_and_aware_clock_required():
    raw = FIXTURE.read_bytes()
    with pytest.raises(ValueError, match="bounded"):
        UntrustedManagementRead.parse(raw + b" " * 65536, now=NOW)
    with pytest.raises(ValueError, match="aware"):
        UntrustedManagementRead.parse(raw, now=NOW.replace(tzinfo=None))
    with pytest.raises(PermissionError, match="bounded observation"):
        UntrustedManagementRead.parse(raw, now=NOW + timedelta(minutes=10))
