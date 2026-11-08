"""One Rust/Python response fixture, typed refusals and no forged authority."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import (
    MAX_RESPONSE_BYTES, UntrustedManagementResponse, make_response,
)

ROOT = Path(__file__).resolve().parents[1] / "contracts/platform"
NOW = datetime(2026, 11, 8, 4, 0, 1, tzinfo=timezone.utc)


def read():
    request = UntrustedManagementRead.parse(
        (ROOT / "management-read-valid-v1.json").read_bytes(), now=NOW
    )
    wire = (ROOT / "management-read-response-valid-v1.json").read_bytes()
    return request, wire


def parse(payload, request=None, now=NOW):
    req = request or read()[0]
    return UntrustedManagementResponse.parse(
        json.dumps(payload).encode("utf-8"), expected=req, now=now
    )


def test_shared_fixture_correlated_untrusted_status():
    request, raw = read()
    obj = UntrustedManagementResponse.parse(raw, expected=request, now=NOW)
    assert obj.outcome == "OK"
    assert obj.generation == 3
    assert obj.denial_code is None
    assert obj.data == {
        "platform_id": "platform:alpha",
        "generation": 3, "operator_stop": False, "core_started": False,
    }


@pytest.mark.parametrize("name,value", [
    ("request_id", "req:other"),
    ("platform_id", "platform:other"),
    ("platform_generation", 4),
    ("platform_generation", True),
    ("operation", "core.start"),
    ("source", "OWNER_APPROVED"),
    ("protocol", "2.0"),
    ("schema", "aegis.platform.management.response.v1"),
    ("outcome", "TRUSTED"),
])
def test_claimed_authority_mismatches_refused(name, value):
    _, raw = read()
    doc = json.loads(raw)
    doc[name] = value
    with pytest.raises((ValueError, PermissionError)):
        parse(doc)


def test_status_never_claims_started_core_or_cleared_stop():
    _, raw = read()
    doc = json.loads(raw)
    for field, forged in (("core_started", True), ("operator_stop", True),
                          ("generation", 12), ("platform_id", "platform:other")):
        other = json.loads(raw)
        other["data"][field] = forged
        with pytest.raises((ValueError, PermissionError)):
            parse(other)


def test_denial_only_for_exact_typed_code_and_null_data():
    req, raw = read()
    doc = json.loads(raw)
    doc["outcome"] = "DENIED"
    doc["data"] = None
    doc["denial"] = {"code": "REVOKED"}
    result = parse(doc)
    assert result.data is None and result.denial_code == "REVOKED"
    for denied in ("SELF_APPROVED", 4, "", "UNKNOWN"):
        wrong = dict(doc, denial={"code": denied})
        with pytest.raises((ValueError, PermissionError)):
            parse(wrong)
    with pytest.raises((ValueError, PermissionError)):
        parse(dict(doc, data={"health": "healthy"}))
    with pytest.raises((ValueError, PermissionError)):
        parse(dict(doc, denial={"code": "REVOKED", "grant": "fake"}))
    assert make_response(
        req, observed_at=NOW, denial_code="NOT_PERMITTED"
    )["outcome"] == "DENIED"


def test_freshness_and_request_deadline_fenced():
    req, raw = read()
    doc = json.loads(raw)
    for when in ("2026-11-08T03:59:57Z", "2026-11-08T04:00:02Z"):
        with pytest.raises(PermissionError):
            parse(dict(doc, observed_at=when))
    with pytest.raises(PermissionError):
        parse(doc, now=NOW + timedelta(seconds=5))
    with pytest.raises((ValueError, PermissionError)):
        parse(dict(doc, observed_at="not-a-date"))


def test_no_unsafe_projections_duplicate_keys_or_unknown_fields():
    req, raw = read()
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementResponse.parse(
            b'{"schema":"forged",' + raw[1:],
            expected=req, now=NOW,
        )
    for item in ({"owner_secret": "leak"}, {"nested": {"__proto__": 4}},
                 {"deep": [[[[[[[[[3]]]]]]]]]},
                 {"tokens": {"api_key": "leak"}}):
        doc = json.loads(raw)
        doc["data"] = item
        with pytest.raises((ValueError, PermissionError)):
            parse(doc)
    doc = json.loads(raw)
    doc["owner_approved"] = True
    with pytest.raises(ValueError):
        parse(doc)
    with pytest.raises(ValueError):
        UntrustedManagementResponse.parse(
            raw + b" " * MAX_RESPONSE_BYTES,
            expected=req, now=NOW,
        )
    with pytest.raises(ValueError):
        UntrustedManagementResponse.parse(
            raw.replace(b"false", b"NaN", 1), expected=req, now=NOW
        )


def test_builder_stays_bounded_and_denies_mixed_outcome():
    req, raw = read()
    data = json.loads(raw)["data"]
    built = make_response(
        req, observed_at=NOW, data=data
    )
    assert parse(built).outcome == "OK"
    with pytest.raises(ValueError):
        make_response(
            req, observed_at=NOW, data=data, denial_code="NOT_PERMITTED"
        )
    with pytest.raises(ValueError):
        make_response(req, observed_at=NOW)
    with pytest.raises(ValueError):
        make_response(req, observed_at=NOW, data={"password": "no"})
    with pytest.raises(ValueError):
        make_response(req, observed_at=datetime(2026,11,8,4), data=data)
