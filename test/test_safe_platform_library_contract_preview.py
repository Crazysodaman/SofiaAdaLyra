"""Pure AG-D028-00 preview boundary; never installs, downloads or grants."""
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from sofia.sdk.platform_management import UntrustedManagementRead

FIX = Path(__file__).resolve().parents[1] / "contracts/platform"
PREFIX = "library-"
RKEYS = {"schema","protocol","request_id","correlation_id","operation",
         "target_platform_id","expected_generation","expected_revision",
         "idempotency_key","created_at","deadline","parameters"}
SKEYS = {"schema","protocol","request_id","correlation_id","operation",
         "platform_id","platform_generation","state_revision","observed_at",
         "outcome","data","denial"}


def sample(name):
    return json.loads((FIX / (PREFIX + name + "-preview-v1.json")).read_text())


def test_preview_is_a_distinct_inert_broker_contract_not_owner_permission():
    ask=sample("request-catalog")
    assert set(ask)==RKEYS
    assert ask["schema"]=="aegis.platform.library.request.v1"
    assert ask["protocol"]=="1.0" and ask["idempotency_key"] is None
    assert ask["expected_generation"] > 0 and ask["expected_revision"] >= 0
    assert not {"caller_principal","audience","owner_secret","peer_sid","peer_uid"} & set(ask)
    with pytest.raises((ValueError,PermissionError)):
        UntrustedManagementRead.parse(
            json.dumps(ask).encode(),now=datetime(2026,11,8,4,0,1,tzinfo=timezone.utc)
        )


def test_catalog_preview_keeps_signed_source_separate_from_install_claims():
    ask=sample("request-catalog")
    seen=sample("response-catalog")
    assert set(seen)==SKEYS
    assert seen["schema"]=="aegis.platform.library.response.v1"
    assert seen["request_id"]==ask["request_id"]
    assert seen["correlation_id"]==ask["correlation_id"]
    assert seen["platform_id"]==ask["target_platform_id"]
    assert seen["platform_generation"]==ask["expected_generation"]
    assert seen["state_revision"]==ask["expected_revision"]
    assert seen["denial"] is None and seen["outcome"]=="OK"
    d=seen["data"]
    assert d["page"]["next_cursor"] is None
    assert d["source"]["kind"]=="LOCAL_VERIFIED_CACHE"
    for item in d["items"]:
        assert len(item["content_digest"])==len(item["manifest_digest"])==64
        assert item["license_distribution"]=="permitted"
        assert "installed" not in item and "active" not in item
        assert "download_url" not in item and "path" not in item
        assert item["signer_key_id"] != d["source"]["source_id"]


def test_stop_preview_contains_no_data_or_owner_secret():
    seen=sample("response-stop")
    assert set(seen)==SKEYS
    assert seen["outcome"]=="DENIED" and seen["data"] is None
    assert seen["denial"]=={"code":"STOPPED"}
    assert "owner" not in json.dumps(seen).lower()


def test_transfer_full_receive_is_not_verified_or_installed():
    seen=sample("response-transfer")
    assert set(seen)==SKEYS
    d=seen["data"]
    assert d["received_bytes"]==d["total_bytes"]
    assert d["verified_bytes"]==0
    assert d["state"]=="VERIFYING"
    assert "installed" not in d and "active" not in d
    assert "token" not in json.dumps(seen).lower()
    assert "resume_url" not in json.dumps(seen).lower()


# Do not silently enable a pending D028 contract by reusing the existing
# management-read parser or a UI preview. Each future route needs a separately
# reviewed versioned service dispatch + SAFE grant + receipt test.
_LIBRARY_OPERATIONS = (
    "library.catalog.snapshot.v1", "library.inventory.snapshot.v1",
    "library.sources.snapshot.v1", "library.transfer.status.v1",
    "library.history.snapshot.v1", "library.plan.acquire.v1",
    "library.acquire.v1", "library.transfer.cancel.v1",
    "library.verify.v1", "library.pin.v1", "library.unpin.v1",
    "library.retire.cache.v1", "library.hub.offer.v1",
    "library.peer.fetch.v1", "library.install.execute.v1",
)


@pytest.mark.parametrize("operation", _LIBRARY_OPERATIONS)
def test_unfrozen_library_operation_cannot_be_smuggled_into_existing_read_broker(operation):
    baseline = json.loads(
        (FIX / "management-read-valid-v1.json").read_text(encoding="utf-8")
    )
    baseline["operation"] = operation
    with pytest.raises(PermissionError, match="read-only"):
        UntrustedManagementRead.parse(
            json.dumps(baseline).encode("utf-8"),
            now=datetime(2026, 11, 8, 4, 0, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("field,value", [
    ("caller_principal", "owner:forged"),
    ("owner_approval", "YES"),
    ("peer_sid", "S-1-5-18"),
    ("download_url", "http://localhost/private"),
    ("auto_activate", True),
])
def test_inert_d028_preview_forbids_client_asserted_authority_fields(field, value):
    ask = sample("request-catalog")
    ask[field] = value
    assert set(ask) != RKEYS
    with pytest.raises((ValueError, PermissionError)):
        UntrustedManagementRead.parse(
            json.dumps(ask).encode("utf-8"),
            now=datetime(2026, 11, 8, 4, 0, 1, tzinfo=timezone.utc),
        )


# D028-00 strict SDK parsing is authority-free. Fixtures are not receipts
# from a publisher, live Hub, native service or installed host.
from sofia.sdk.platform_library import UntrustedLibraryRequest, UntrustedLibraryResponse

UTC_NOW = datetime(2026, 11, 8, 4, 0, 2, tzinfo=timezone.utc)


def _wire(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True).encode()


def _request(name="request-catalog"):
    return UntrustedLibraryRequest.parse(_wire(sample(name)), now=UTC_NOW)


def test_library_sdk_parses_correlated_catalog_and_typed_stop_as_untrusted():
    request = _request()
    reply = UntrustedLibraryResponse.parse(
        _wire(sample("response-catalog")), expected=request, now=UTC_NOW,
    )
    assert reply.outcome == "OK" and reply.revision == 12
    assert reply.data["items"][0]["signer_key_id"] == "key:test-only"
    assert "installed" not in reply.data["items"][0]
    denied = UntrustedLibraryResponse.parse(
        _wire(sample("response-stop")), expected=request, now=UTC_NOW,
    )
    assert denied.outcome == "DENIED" and denied.denial_code == "STOPPED"
    assert denied.data is None


def test_library_transfer_complete_bytes_are_not_installed_or_verified():
    req = _request("request-transfer")
    actual = UntrustedLibraryResponse.parse(
        _wire(sample("response-transfer")), expected=req, now=UTC_NOW,
    )
    assert actual.data["received_bytes"] == actual.data["total_bytes"]
    assert actual.data["verified_bytes"] == 0
    assert actual.data["state"] == "VERIFYING"
    assert "installed" not in actual.data and "active" not in actual.data


@pytest.mark.parametrize("field,value", [
    ("protocol", "1.1"),
    ("protocol", "2.0"),
    ("target_platform_id", "platform:other"),
    ("expected_generation", 0),
    ("expected_generation", 2**53),
    ("expected_revision", -1),
    ("idempotency_key", "self-approved"),
    ("deadline", "2026-11-08T04:00:01Z"),
    ("operation", "library.install.execute.v1"),
])
def test_library_request_version_scope_and_time_fail_closed(field, value):
    original = sample("request-catalog")
    original[field] = value
    with pytest.raises((ValueError, PermissionError)):
        UntrustedLibraryRequest.parse(_wire(original), now=UTC_NOW)


@pytest.mark.parametrize("field,value", [
    ("protocol", "2.0"),
    ("request_id", "req:forged"),
    ("correlation_id", "corr:other"),
    ("platform_id", "platform:other"),
    ("platform_generation", 8),
    ("state_revision", 13),
    ("observed_at", "2026-11-08T04:00:09Z"),
    ("outcome", "SELF_APPROVED"),
])
def test_library_response_correlation_and_freshness_fail_closed(field, value):
    response = sample("response-catalog")
    response[field] = value
    with pytest.raises((ValueError, PermissionError)):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=_request(), now=UTC_NOW,
        )


@pytest.mark.parametrize("missing", [
    "data", "denial", "state_revision", "correlation_id",
])
def test_library_v1_requires_every_envelope_key(missing):
    response = sample("response-catalog")
    del response[missing]
    with pytest.raises(ValueError, match="missing"):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=_request(), now=UTC_NOW,
        )


def test_library_refuses_source_claims_as_install_or_publisher_authority():
    response = sample("response-catalog")
    bad = response["data"]["items"][0]
    bad["installed"] = True
    with pytest.raises(ValueError):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=_request(), now=UTC_NOW,
        )
    del bad["installed"]
    bad["license_distribution"] = "non_redistributable"
    with pytest.raises(PermissionError, match="restricted"):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=_request(), now=UTC_NOW,
        )
    bad["license_distribution"] = "permitted"
    response["data"]["source"]["status"] = "CURRENT"
    response["data"]["catalog_fresh_until"] = "2026-11-08T03:00:00Z"
    with pytest.raises(PermissionError, match="fresh"):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=_request(), now=UTC_NOW,
        )


def test_library_transfer_progress_is_bounded_and_never_installs():
    req = _request("request-transfer")
    response = sample("response-transfer")
    response["data"]["state"] = "COMPLETE"
    with pytest.raises(ValueError, match="completion"):
        UntrustedLibraryResponse.parse(_wire(response), expected=req, now=UTC_NOW)
    response["data"]["state"] = "VERIFYING"
    response["data"]["verified_bytes"] = 4097
    with pytest.raises(ValueError, match="progress"):
        UntrustedLibraryResponse.parse(_wire(response), expected=req, now=UTC_NOW)
    response["data"]["verified_bytes"] = 0
    response["data"]["source_platform_id"] = "platform:attacker"
    # An untrusted source-identity string remains syntax only: it cannot
    # prove enrollment or current SAFE authority at a transport boundary.
    observed = UntrustedLibraryResponse.parse(
        _wire(response), expected=req, now=UTC_NOW,
    )
    assert observed.data["source_platform_id"] == "platform:attacker"


def test_library_rejects_duplicate_json_and_surrogate_tricks():
    request = _request()
    response = sample("response-catalog")
    raw = _wire(response)
    with pytest.raises(ValueError, match="duplicate"):
        UntrustedLibraryResponse.parse(
            b'{"schema":"forged",' + raw[1:],
            expected=request, now=UTC_NOW,
        )
    response["data"]["items"][0]["publisher"] = "\ud800"
    with pytest.raises(ValueError, match="unsafe"):
        UntrustedLibraryResponse.parse(
            _wire(response), expected=request, now=UTC_NOW,
        )


def test_d028_peer_requires_actual_mutually_authenticated_tls_not_a_fake_identity(tmp_path):
    from sofia.platform.run.library_peer_gate import admit_owner_enrolled_library_chunk
    from sofia.platform.safe.permissions import PermissionStore, capability_permission_policy
    from sofia.platform.safe.operator_stop import OperatorStopStore
    from test.test_platform_service_session import provision

    identity, current, state = provision(tmp_path)
    permissions = PermissionStore(state)
    stop = OperatorStopStore(state)
    assert capability_permission_policy("library.peer.fetch").standing_grant_allowed is False
    host = current.identity.canonical_uuid
    status = {
        "platform_id": host, "generation": 1,
        "operator_stop": False, "core_started": False,
    }
    arguments = dict(
        tls_socket=object(), permissions=permissions, stop=stop,
        current_status=lambda: status,
        source_platform_id="platform:peer-fixture",
        target_platform_id=host,
        expected_generation=1, catalog_revision=2,
        manifest_digest="a" * 64, content_digest="b" * 64,
        artifact_kind="module", offset=0, length=4096,
        total_bytes=4096,
    )
    with pytest.raises(PermissionError, match="real OS TLS"):
        admit_owner_enrolled_library_chunk(**arguments)
    with pytest.raises(ValueError, match="out of declared bounds"):
        admit_owner_enrolled_library_chunk(**{**arguments, "offset": 1000})
    with pytest.raises(ValueError, match="signed pinned digest"):
        admit_owner_enrolled_library_chunk(
            **{**arguments, "content_digest": "signed-by-hub-only"}
        )
    with pytest.raises(ValueError, match="bounded"):
        admit_owner_enrolled_library_chunk(**{**arguments, "length": 10 * 1024 * 1024})
