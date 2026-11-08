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
