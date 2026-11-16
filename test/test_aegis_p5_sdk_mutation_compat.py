"""Aegis P5 management-mutation SDK strictness and version compatibility.

The wire adapter must accept only the exact reviewed protocol version and must
reject unknown, duplicate, oversized or control-bearing JSON before any effect.
"""
from __future__ import annotations

import json

import pytest

from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_RESPONSE_SCHEMA,
    MAX_MUTATION_REQUEST_BYTES, UntrustedManagementMutation,
    UntrustedManagementMutationResponse,
)
from test.aegis_p5_security_support import NOW, request_document


def _typed(document: dict[str, object]) -> UntrustedManagementMutation:
    return UntrustedManagementMutation.from_payload(document, now=NOW)


def _response(request: UntrustedManagementMutation, **changes):
    document = {
        "schema": MANAGEMENT_MUTATION_RESPONSE_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": request.request_id,
        "correlation_id": request.correlation_id,
        "idempotency_key": request.idempotency_key,
        "platform_id": request.target_platform_id,
        "operation": request.operation,
        "outcome": "SUCCEEDED",
        "receipt_id": "mutreceipt:p5",
        "current_generation": 3,
        "current_revision": 1,
        "error_code": None,
        "detail": None,
        "observed_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    document.update(changes)
    return document


@pytest.mark.parametrize(
    "version", ["1.0", "1", "1.0.0", "1.1", "2.0", "0.9", "", " 1.0"],
)
def test_management_mutation_protocol_versions_are_exact(version):
    document = request_document(protocol_version=version)
    if version == MANAGEMENT_MUTATION_PROTOCOL:
        assert _typed(document).protocol_version == "1.0"
    else:
        with pytest.raises(ValueError, match="unsupported"):
            _typed(document)


def test_management_mutation_response_protocol_versions_are_exact():
    request = _typed(request_document())
    for version in (MANAGEMENT_MUTATION_PROTOCOL, "1.1", "2.0", "1.0.0"):
        document = _response(request, protocol_version=version)
        raw = json.dumps(document, separators=(",", ":")).encode("utf-8")
        if version == MANAGEMENT_MUTATION_PROTOCOL:
            parsed = UntrustedManagementMutationResponse.parse(
                raw, expected=request, now=NOW,
            )
            assert parsed.outcome == "SUCCEEDED"
        else:
            with pytest.raises(PermissionError, match="uncorrelated"):
                UntrustedManagementMutationResponse.parse(
                    raw, expected=request, now=NOW,
                )


def test_management_mutation_rejects_unknown_and_duplicate_fields():
    document = request_document()
    document["grant"] = "owner"
    with pytest.raises(ValueError, match="unreviewed"):
        _typed(document)

    duplicate = (
        b'{"schema":"aegis.platform.management_mutation.v1",'
        b'"schema":"aegis.platform.management_mutation.v1"}'
    )
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementMutation.parse(duplicate, now=NOW)

    nested_duplicate = json.dumps(
        request_document(), separators=(",", ":"),
    ).replace('"payload":{"value":"exact"}', '"payload":{"value":"a","value":"b"}')
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementMutation.parse(nested_duplicate.encode("utf-8"), now=NOW)


def test_management_mutation_rejects_oversized_control_and_nonfinite_json():
    oversized = json.dumps(
        request_document(payload={"value": "a" * (MAX_MUTATION_REQUEST_BYTES + 1)}),
        separators=(",", ":"),
    ).encode("utf-8")
    with pytest.raises(ValueError, match="bounded bytes"):
        UntrustedManagementMutation.parse(oversized, now=NOW)

    for document in (
        request_document(payload={"value": "line\x01break"}),
        request_document(payload={"bad\x01key": "value"}),
        request_document(payload={"value": "\ud800"}),
    ):
        with pytest.raises(ValueError, match="invalid|control|surrogate"):
            UntrustedManagementMutation.parse(
                json.dumps(document, separators=(",", ":")).encode("utf-8"),
                now=NOW,
            )

    nonfinite = json.dumps(
        request_document(payload={"value": 1}), separators=(",", ":"),
    ).replace('"value":1', '"value":NaN').encode("utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        UntrustedManagementMutation.parse(nonfinite, now=NOW)


def test_management_mutation_response_rejects_unknown_duplicate_and_control():
    request = _typed(request_document())
    good = _response(request)
    assert UntrustedManagementMutationResponse.parse(
        json.dumps(good, separators=(",", ":")).encode("utf-8"),
        expected=request, now=NOW,
    ).outcome == "SUCCEEDED"

    for field, value in (
        ("grant", "owner"),
        ("outcome", "OK"),
        ("detail", "line\x01break"),
        ("error_code", "UNREVIEWED"),
    ):
        tampered = dict(good)
        tampered[field] = value
        with pytest.raises((ValueError, PermissionError)):
            UntrustedManagementMutationResponse.parse(
                json.dumps(tampered, separators=(",", ":")).encode("utf-8"),
                expected=request, now=NOW,
            )

    duplicate = json.dumps(good, separators=(",", ":"))[:-1] + (
        ',"outcome":"SUCCEEDED"}'
    )
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedManagementMutationResponse.parse(
            duplicate.encode("utf-8"), expected=request, now=NOW,
        )
