"""Portainer metadata must stay scoped to exact stack and secret-free."""
import pytest
from sofia.modules.it_containers.stack_summary import summarize_stack_metadata

META = {
    "Id": 19, "EndpointId": 7, "Name": "mealie", "Type": 2,
    "Status": 1, "GitConfig": {"Password": "TOP_SECRET"},
    "Env": [{"name": "API_KEY", "value": "SUPER_SECRET"}],
    "StackFileContent": "password: SUPER_SECRET",
}


def test_metadata_has_no_secrets_or_fake_health():
    result = summarize_stack_metadata(META, stack_id=19, endpoint_id=7)
    assert result["source_class"] == "git"
    assert result["stack_id"] == 19 and result["endpoint_id"] == 7
    assert result["effect"] == "none"
    assert result["runtime_health_verified"] is False
    assert "SECRET" not in str(result)
    assert "Env" not in result and "GitConfig" not in result


def test_source_is_unknown_without_evidence():
    plain = {k: v for k, v in META.items() if k != "GitConfig"}
    assert summarize_stack_metadata(plain, stack_id=19, endpoint_id=7)["source_class"] == "unknown"
    plain["GitConfig"] = None
    assert summarize_stack_metadata(plain, stack_id=19, endpoint_id=7)["source_class"] == "not_git_evidenced"


@pytest.mark.parametrize("mutation,stack_id,endpoint_id", [
    ({"Id": 20}, 19, 7), ({"EndpointId": 8}, 19, 7),
    ({"Id": True}, 19, 7), ({"EndpointId": True}, 19, 7),
    ({"Name": "new\nline"}, 19, 7), ({"Name": ""}, 19, 7),
    ({"Status": "running"}, 19, 7), ({"Type": -1}, 19, 7),
    ({}, True, 7), ({}, 19, 0),
])
def test_invalid_identity_or_metadata_fails_closed(mutation, stack_id, endpoint_id):
    with pytest.raises(ValueError):
        summarize_stack_metadata(META | mutation, stack_id=stack_id, endpoint_id=endpoint_id)
