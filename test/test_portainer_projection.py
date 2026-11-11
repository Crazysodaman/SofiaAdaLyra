"""Fail-closed, effect-free Portainer metadata projection tests."""
import pytest

from sofia.modules.integrations.portainer_projection import (
    project_portainer_stack_metadata,
)


def _stack():
    return {
        "Id": 7, "EndpointId": 3, "Name": "Mealie", "Status": 1,
        "GitConfig": {"URL": "https://private.example/repo.git", "Authentication": {"Password": "GIT_SECRET"}},
        "Env": [{"name": "API_KEY", "value": "PORTAINER_SECRET"}],
        "StackFileContent": "PASSWORD: COMPOSE_SECRET",
        "Webhook": "WEBHOOK_SECRET",
        "ResourceControl": {"AdministratorsOnly": True},
    }


def test_allowlisted_stack_metadata_has_no_secret_content():
    result = project_portainer_stack_metadata(_stack(), stack_id=7, endpoint_id=3)
    assert result == {
        "stack_id": 7, "endpoint_id": 3, "name": "Mealie",
        "source_hint": "git", "raw_status_code": 1,
        "evidence_class": "portainer_metadata_unverified_health",
    }
    assert "SECRET" not in repr(result)
    assert "private.example" not in repr(result)


@pytest.mark.parametrize("patch,stack_id,endpoint_id", [
    ({"Id": 8}, 7, 3),
    ({"EndpointId": 2}, 7, 3),
    ({"Id": "7"}, 7, 3),
    ({"Id": True}, 7, 3),
    ({"EndpointId": False}, 7, 3),
    ({"Name": "evil\x1b[31m"}, 7, 3),
    ({"Name": ""}, 7, 3),
    ({"Name": "x" * 129}, 7, 3),
    ({"GitConfig": "bogus"}, 7, 3),
    ({"Status": "running"}, 7, 3),
    ({"Status": True}, 7, 3),
    ({"Status": -1}, 7, 3),
    ({}, 0, 3),
    ({}, 7, 0),
    ({}, True, 3),
])
def test_bad_or_mismatched_metadata_fails_closed(patch, stack_id, endpoint_id):
    data = _stack() | patch
    with pytest.raises(ValueError):
        project_portainer_stack_metadata(data, stack_id=stack_id, endpoint_id=endpoint_id)


def test_absent_git_metadata_is_unknown_not_assumed_editor():
    data = _stack()
    data.pop("GitConfig")
    result = project_portainer_stack_metadata(data, stack_id=7, endpoint_id=3)
    assert result["source_hint"] == "unknown"
    assert result["raw_status_code"] == 1
    assert "healthy" not in repr(result)


def test_nonmapping_payload_is_rejected():
    with pytest.raises(ValueError):
        project_portainer_stack_metadata([], stack_id=7, endpoint_id=3)


def test_empty_git_configuration_does_not_prove_git_management():
    data = _stack()
    data["GitConfig"] = {}
    result = project_portainer_stack_metadata(data, stack_id=7, endpoint_id=3)
    assert result["source_hint"] == "unknown"
