"""Strict Rust/Python Platform management response matching and denial."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_reply import UntrustedManagementReply

pytestmark = pytest.mark.pkg_ui
ROOT = Path(__file__).resolve().parents[1] / "contracts/platform"
NOW = datetime(2026, 11, 8, 4, 0, 1, tzinfo=timezone.utc)


def fixture():
    request = UntrustedManagementRead.parse(
        (ROOT / "management-read-valid-v1.json").read_bytes(), now=NOW
    )
    response = json.loads(
        (ROOT / "management-read-response-valid-v1.json").read_text(encoding="utf-8")
    )
    return request, response


def test_fixture_matches_request_but_never_claims_authenticated_transport():
    req, doc = fixture()
    output = UntrustedManagementReply.parse(
        json.dumps(doc).encode(), request=req, now=NOW
    )
    assert output.generation == 3
    assert output.request_id == req.request_id
    assert output.operation == "platform.status"
    assert output.payload["health"] == "unknown"
    assert not hasattr(output, "authenticated")


@pytest.mark.parametrize("change", [
    {"request_id": "req:different"},
    {"platform_id": "platform:other"},
    {"generation": 4},
    {"generation": True},
    {"operation": "module.list"},
])
def test_wrong_identity_generation_or_operation_denied(change):
    req, doc = fixture()
    doc.update(change)
    with pytest.raises(PermissionError, match="does not match"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )


@pytest.mark.parametrize("change", [
    {"observed_at": "2026-11-08T04:00:05Z"},
    {"observed_at": "2026-11-08T03:50:00Z"},
    {"observed_at": "2026-11-08T04:00:04Z"},
])
def test_stale_future_or_deadline_observations_denied(change):
    req, doc = fixture()
    doc.update(change)
    with pytest.raises(PermissionError, match="stale or future"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )


def test_extra_owner_grant_and_duplicate_json_are_refused():
    req, doc = fixture()
    doc["owner_approved"] = True
    with pytest.raises(ValueError, match="unknown"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementReply.parse(
            b'{"schema":"a","schema":"b"}', request=req, now=NOW
        )


def test_nested_secret_prototype_and_unreviewed_payload_denied():
    req, doc = fixture()
    doc["payload"] = {"data": [{"private_key": "nope"}]}
    with pytest.raises(ValueError, match="unsafe"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )
    doc["payload"] = {"__proto__": {"admin": True}}
    with pytest.raises(ValueError, match="unsafe"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )
    doc["payload"] = "not-an-object"
    with pytest.raises(ValueError, match="scoped object"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )


def test_oversized_and_future_receiver_clock_denied():
    req, doc = fixture()
    doc["payload"] = {"data": "x" * (32 * 1024)}
    with pytest.raises(ValueError, match="bounded"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req, now=NOW
        )
    _, doc = fixture()
    with pytest.raises(ValueError, match="aware"):
        UntrustedManagementReply.parse(
            json.dumps(doc).encode(), request=req,
            now=NOW.replace(tzinfo=None)
        )
