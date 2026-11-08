"""Source-level Portainer projection regression; no provider or Docker access."""
from datetime import datetime, timezone
import json

import pytest

from sofia.modules.it_containers.portainer_projection import project_portainer_stacks

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def stack(**updates):
    return {
        "Id": 42, "Name": "mealie", "EndpointId": 7,
        "Status": 1,
        "Env": [{"name": "DATABASE_PASSWORD", "value": "do-not-expose"}],
        "GitConfig": {"Authentication": {"Password": "do-not-expose"}},
        "StackFileContent": "services: {x: {environment: [SECRET=do-not-expose]}}",
        "AccessControl": {"secret": "do-not-expose"},
    } | updates


def test_portainer_stack_projection_never_leaks_secret_bearing_fields():
    payload = project_portainer_stacks([stack()], endpoint_id=7, observed_at=NOW)
    result = json.dumps(payload)
    assert "do-not-expose" not in result
    assert "StackFileContent" not in result
    assert "GitConfig" not in result
    assert "Env" not in result
    assert payload["effect"] == "none"
    assert payload["source_verified"] is False
    assert payload["secret_fields_exposed"] is False
    assert payload["stacks"] == [{
        "stack_id": 42,
        "name": "mealie",
        "portainer_status_code": 1,
        "runtime_health": "UNKNOWN",
        "deployment_verified": False,
    }]


def test_stack_inventory_orders_by_stable_identity_and_does_not_prove_health():
    projected = project_portainer_stacks([
        stack(Id=90, Name="later", Status=123456789),
        stack(Id=1, Name="earlier", Status="running"),
    ], endpoint_id=7, observed_at=NOW)
    assert [x["stack_id"] for x in projected["stacks"]] == [1, 90]
    assert all(x["runtime_health"] == "UNKNOWN" for x in projected["stacks"])
    assert all(x["portainer_status_code"] is None for x in projected["stacks"])


@pytest.mark.parametrize("bad_endpoint", [0, -1, True, "7", 1000000001])
def test_rejects_invalid_endpoint_ids(bad_endpoint):
    with pytest.raises(ValueError):
        project_portainer_stacks([stack()], endpoint_id=bad_endpoint, observed_at=NOW)


@pytest.mark.parametrize("bad_stack", [
    stack(Id=0), stack(Id=True), stack(Id="42"), stack(EndpointId=8),
    stack(EndpointId=None), stack(Name=""), stack(Name="bad\x1b[32m"),
    stack(Name=" bad"), stack(Name="bad\nline"),
])
def test_rejects_invalid_stack_metadata(bad_stack):
    with pytest.raises(ValueError):
        project_portainer_stacks([bad_stack], endpoint_id=7, observed_at=NOW)


def test_rejects_duplicate_ids_and_unbounded_inventory():
    with pytest.raises(ValueError):
        project_portainer_stacks([stack(), stack(Name="copy")],
                                endpoint_id=7, observed_at=NOW)
    with pytest.raises(ValueError):
        project_portainer_stacks([stack(Id=n + 1) for n in range(257)],
                                endpoint_id=7, observed_at=NOW)
    with pytest.raises(ValueError):
        project_portainer_stacks([{}], endpoint_id=7, observed_at=NOW)


def test_rejects_naive_timestamp_and_non_list_input():
    with pytest.raises(ValueError):
        project_portainer_stacks([], endpoint_id=7,
                                observed_at=datetime(2026, 11, 8))
    with pytest.raises(ValueError):
        project_portainer_stacks((), endpoint_id=7, observed_at=NOW)
