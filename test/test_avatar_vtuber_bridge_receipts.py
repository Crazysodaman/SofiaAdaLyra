"""MOD-VTUBER-BRIDGE supplied adapter capability/receipt boundary tests."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.avatar.vtuber_bridge_receipts import (
    capability_registrations, review_vtuber_bridge_receipts,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def adapter(**change):
    data = {
        "adapter_id": "vtube:local",
        "adapter_version": "1.0.0",
        "protocol": "VTubeStudioPublicAPI",
        "transport": "localhost",
        "authenticated": True,
        "model_loaded": True,
        "capabilities": [
            "api_status", "current_model", "input_parameter_list",
            "inject_parameter_data", "trigger_hotkey",
        ],
    }
    data.update(change)
    return data


def receipt(receipt_id="receipt:1", **change):
    requested = change.pop("requested_at", NOW - timedelta(seconds=2))
    completed = change.pop("completed_at", NOW - timedelta(seconds=1))
    data = {
        "receipt_id": receipt_id,
        "operation": "api_status",
        "requested_at": (
            requested.isoformat() if hasattr(requested, "isoformat") else requested
        ),
        "completed_at": (
            completed.isoformat() if hasattr(completed, "isoformat") else completed
        ),
        "accepted": True,
        "frame_count": 0,
        "audience": "public",
    }
    data.update(change)
    return data


def snapshot(receipts=None, adapter_record=None, **change):
    data = {
        "source_ref": "vtube:local",
        "observed_at": NOW.isoformat(),
        "audience": "public",
        "private_audience_claimed": False,
        "adapter": adapter_record if adapter_record is not None else adapter(),
        "receipts": receipts if receipts is not None else [receipt()],
    }
    data.update(change)
    return data


def test_supplied_adapter_receipts_validate_without_live_connection_or_animation_claim():
    report = review_vtuber_bridge_receipts(snapshot([
        receipt("receipt:status", operation="api_status"),
        receipt(
            "receipt:frame", operation="inject_parameter_data",
            frame_count=4,
        ),
    ]), now=NOW)
    assert report["status"] == "reviewed"
    assert report["counts"] == {
        "receipt_validated": 1,
        "reported_frame_unverified": 1,
        "rejected": 0,
        "restricted": 0,
        "undeclared_capability": 0,
    }
    rows = {row["receipt_id"]: row for row in report["receipts"]}
    assert rows["receipt:status"]["outcome"] == "receipt_validated"
    assert rows["receipt:frame"]["outcome"] == "reported_frame_unverified"
    assert rows["receipt:frame"]["flags"] == ["animation_not_authenticated"]
    assert report["adapter"]["capabilities"] == [
        "api_status", "current_model", "inject_parameter_data",
        "input_parameter_list", "trigger_hotkey",
    ]
    assert report["effect"] == "none"
    assert report["evidence_class"] == "supplied_unverified"
    assert report["live_connection_opened"] is False
    assert report["renderer_launched"] is False
    assert report["frame_authenticated"] is False
    assert report["animation_claimed"] is False
    assert report["adapter_control_sent"] is False


def test_rejected_and_undeclared_adapter_operations_never_render():
    report = review_vtuber_bridge_receipts(snapshot(
        [
            receipt("receipt:rejected", accepted=False),
            receipt(
                "receipt:undeclared", operation="trigger_hotkey",
                frame_count=2,
            ),
        ],
        adapter_record=adapter(capabilities=["api_status"]),
    ), now=NOW)
    rows = {row["receipt_id"]: row for row in report["receipts"]}
    assert rows["receipt:rejected"]["outcome"] == "rejected"
    assert rows["receipt:undeclared"]["outcome"] == "undeclared_capability"
    assert rows["receipt:undeclared"]["flags"] == ["adapter_capability_not_declared"]
    assert report["counts"]["rejected"] == 1
    assert report["counts"]["undeclared_capability"] == 1
    assert report["animation_claimed"] is False
    assert report["frame_authenticated"] is False


@pytest.mark.parametrize("change", [
    {"operation": "load_model"},
    {"operation": "current_model", "frame_count": 2},
    {"requested_at": "not-a-date"},
    {"requested_at": "2026-11-16T12:00:00"},
    {"completed_at": NOW - timedelta(seconds=3)},
    {"accepted": False, "frame_count": 2},
    {"frame_count": 241},
    {"frame_count": True},
    {"receipt_id": "C:/Users/alice/vts_receipt.json"},
    {"receipt_id": "token:prod"},
    {"receipt_id": "a/../../secret"},
    {"note": "x" * 281},
    {"note": "line\nbreak"},
    {"extra": "field"},
])
def test_receipt_rejects_malformed_or_unsafe_records(change):
    with pytest.raises(ValueError):
        review_vtuber_bridge_receipts(snapshot([receipt(**change)]), now=NOW)


@pytest.mark.parametrize("change", [
    {"adapter_version": "1.0"},
    {"adapter_version": "v1.0.0"},
    {"protocol": "OtherProtocol"},
    {"transport": "remote"},
    {"authenticated": 1},
    {"model_loaded": "yes"},
    {"capabilities": "api_status"},
    {"capabilities": ["load_model"]},
    {"capabilities": ["api_status", "api_status"]},
    {"capabilities": [
        "api_status", "current_model", "input_parameter_list",
        "inject_parameter_data", "trigger_hotkey", "api_status", "current_model",
        "input_parameter_list", "inject_parameter_data", "trigger_hotkey",
        "api_status", "current_model", "input_parameter_list",
        "inject_parameter_data", "trigger_hotkey", "api_status", "current_model",
    ]},
    {"adapter_id": "C:/Users/alice/vts"},
    {"extra": "field"},
])
def test_adapter_capability_rejects_malformed_or_unknown_declarations(change):
    with pytest.raises(ValueError):
        review_vtuber_bridge_receipts(
            snapshot(adapter_record=adapter(**change)), now=NOW,
        )


@pytest.mark.parametrize("bad", [
    {"receipts": []},
    {"receipts": [receipt(f"receipt:{index}") for index in range(65)]},
    {"receipts": [receipt("same"), receipt("same")]},
    {"receipts": [receipt(audience="private")]},
    {"receipts": [receipt(completed_at=NOW + timedelta(minutes=5))]},
    {"source_ref": "C:/Users/alice/vts"},
    {"source_ref": "token:prod"},
    {"observed_at": "not-a-date"},
    {"observed_at": "2026-11-16T12:00:00"},
    {"audience": "friends"},
    {"private_audience_claimed": "yes"},
    {"body": "private avatar art"},
])
def test_snapshot_rejects_malformed_duplicate_oversized_or_unsafe_records(bad):
    with pytest.raises(ValueError):
        review_vtuber_bridge_receipts(snapshot(**bad), now=NOW)


@pytest.mark.parametrize("observed", [
    NOW - timedelta(hours=1),
    NOW + timedelta(minutes=1),
])
def test_stale_or_future_snapshot_is_truthfully_unknown(observed):
    row = receipt(
        requested_at=observed - timedelta(seconds=2),
        completed_at=observed - timedelta(seconds=1),
    )
    report = review_vtuber_bridge_receipts(
        snapshot([row], observed_at=observed.isoformat()), now=NOW,
    )
    assert report["status"] == "unknown"
    assert report["counts"] == {}
    assert report["receipts"] == []
    assert report["live_connection_opened"] is False
    assert report["animation_claimed"] is False


def test_private_receipts_require_supplied_private_audience():
    private = receipt("receipt:private-audience", audience="private")
    with pytest.raises(ValueError, match="private adapter receipt"):
        review_vtuber_bridge_receipts(snapshot([private]), now=NOW)
    restricted = review_vtuber_bridge_receipts(snapshot(
        [private], audience="private",
    ), now=NOW)
    assert restricted["counts"]["restricted"] == 1
    assert restricted["receipts"][0]["outcome"] == "restricted"
    assert restricted["receipts"][0]["note"] is None
    assert restricted["animation_claimed"] is False
    allowed = review_vtuber_bridge_receipts(snapshot(
        [private], audience="private", private_audience_claimed=True,
    ), now=NOW)
    assert allowed["counts"]["receipt_validated"] == 1
    assert allowed["receipts"][0]["outcome"] == "receipt_validated"


def test_sensitive_receipt_notes_are_redacted():
    report = review_vtuber_bridge_receipts(snapshot([
        receipt("receipt:one", note="token=abc123 C:\\Users\\alice\\frame.png"),
        receipt(
            "receipt:two",
            note="secret=hunter2 /home/bob/avatar.png alice@example.com",
        ),
    ]), now=NOW)
    assert report["redactions"] >= 4
    serialized = json.dumps(report)
    for secret in ("abc123", "Users", "/home/bob", "hunter2", "alice@example.com"):
        assert secret not in serialized
    assert "<redacted>" in serialized
    assert report["evidence_class"] == "supplied_unverified"


def test_capability_registration_shape_and_exact_parameters():
    registrations = capability_registrations()
    assert isinstance(registrations, tuple) and len(registrations) == 1
    capability, handler = registrations[0]
    assert isinstance(capability, Capability) and callable(handler)
    live = datetime.now(timezone.utc)
    payload = snapshot([receipt(
        requested_at=live - timedelta(seconds=2),
        completed_at=live - timedelta(seconds=1),
    )], observed_at=live.isoformat())
    result = handler(CapabilityRequest(
        capability, {"snapshot": payload}, None, "review adapter receipts",
    ))
    assert result["status"] == "reviewed"
    assert result["effect"] == "none"
    assert result["animation_claimed"] is False
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            Capability(capability.name, "Forged descriptor"),
            {"snapshot": payload}, None, "forged",
        ))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, dict({"snapshot": payload}, connect=True), None, "invalid",
        ))
