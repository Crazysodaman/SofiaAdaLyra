"""Cross-language strict Platform status reply correlation is not authorization."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import UntrustedManagementStatus

ROOT = Path(__file__).resolve().parents[1] / "contracts/platform"
NOW = datetime(2026, 11, 8, 4, tzinfo=timezone.utc)


def valid():
    request = UntrustedManagementRead.parse(
        (ROOT / "management-read-valid-v1.json").read_bytes(), now=NOW
    )
    return request, (ROOT / "management-status-valid-v1.json").read_bytes()


def test_shared_rust_fixture_parses_without_claiming_transport_authentication():
    request, response = valid()
    observed = UntrustedManagementStatus.parse(response, expected=request)
    assert observed.request_id == request.request_id
    assert observed.platform_id == request.target_platform_id
    assert observed.generation == request.expected_generation
    assert observed.operator_stop is False
    assert observed.core_started is False
    assert not hasattr(observed, "authenticated")


@pytest.mark.parametrize("field,value", [
    ("platform_generation", 4),
    ("request_id", "req:wrong"),
    ("platform_id", "platform:wrong"),
    ("source", "self-authorized"),
    ("operation", "module.remove"),
    ("protocol", "2.0"),
])
def test_correlation_forgery_denied(field, value):
    expected, raw = valid()
    payload = json.loads(raw)
    payload[field] = value
    with pytest.raises(ValueError):
        UntrustedManagementStatus.parse(
            json.dumps(payload).encode(), expected=expected
        )


@pytest.mark.parametrize("field,value", [
    ("operator_stop", True),
    ("core_started", True),
    ("generation", 4),
    ("platform_id", "platform:wrong"),
])
def test_stale_or_not_ready_observation_denied(field, value):
    expected, raw = valid()
    payload = json.loads(raw)
    payload["data"][field] = value
    with pytest.raises(ValueError):
        UntrustedManagementStatus.parse(
            json.dumps(payload).encode(), expected=expected
        )


def test_unknown_grant_duplicate_key_and_oversized_response_denied():
    expected, raw = valid()
    payload = json.loads(raw)
    payload["owner_approved"] = True
    with pytest.raises(ValueError):
        UntrustedManagementStatus.parse(
            json.dumps(payload).encode(), expected=expected
        )
    duplicate = b'{"schema":"fake",' + raw[1:]
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementStatus.parse(duplicate, expected=expected)
    with pytest.raises(ValueError, match="bound"):
        UntrustedManagementStatus.parse(raw + b"x" * 65536, expected=expected)


def test_nonfinite_json_and_wrong_operation_denied():
    expected, raw = valid()
    with pytest.raises(ValueError):
        UntrustedManagementStatus.parse(
            raw.replace(b"false", b"NaN", 1), expected=expected
        )
    payload = expected.to_payload()
    payload["operation"] = "settings.inspect"
    request = UntrustedManagementRead.from_payload(payload, now=NOW)
    with pytest.raises(ValueError, match="status request"):
        UntrustedManagementStatus.parse(raw, expected=request)
