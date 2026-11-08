"""Both stack capabilities must be scoped, authenticated by dispatch and redacted."""
from datetime import datetime, timezone
import json

import pytest

from sofia.modules.integrations.portainer import PortainerAdapter
from sofia.modules.integrations.portainer_projection import project_portainer_stacks
from sofia.modules.integrations.capabilities import create_configured_integration_tools
from sofia.platform.capability.model import CapabilityRequest, CapabilityResultKind
from sofia.platform.capability.system import CapabilitySystem
from sofia.platform.safe.permissions import PermissionLevel, capability_permission_policy
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

NOW = datetime(2026, 11, 8, 12, tzinfo=timezone.utc)
SECRET = "NEVER_FORWARD_COMPOSE_PASSWORD"


def stack(**extra):
    return {
        "Id": 23, "EndpointId": 7, "Name": "mealie", "Status": 1,
        "GitConfig": {"URL": "https://credentials.invalid/private",
                      "Authentication": {"Password": SECRET}},
        "Env": [{"name": "DB_PASSWORD", "value": SECRET}],
        "StackFileContent": SECRET,
        "Webhook": SECRET, "ResourceControl": {"Secret": SECRET},
    } | extra


class FakeHttp:
    def __init__(self):
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/api/stacks":
            return [stack()]
        if path == "/api/stacks/23":
            return stack()
        raise AssertionError("unexpected path or effect")


def test_single_and_bulk_use_same_redaction_contract():
    port = PortainerAdapter("https://example.invalid", "test-key", 7)
    port.http = FakeHttp()
    bulk = port.stacks()
    single = port.stack_summary(23)
    assert port.stack_inventory_summary()["stacks"] == bulk["stacks"]
    assert bulk["stacks"] == [{
        "stack_id": 23, "name": "mealie", "portainer_status_code": 1,
        "runtime_health": "UNKNOWN", "deployment_verified": False,
    }]
    assert single["stack_id"] == 23
    assert single["evidence_class"] == "portainer_metadata_unverified_health"
    assert bulk["source_verified"] is False and bulk["effect"] == "none"
    for result in (bulk, single):
        serialized = json.dumps(result)
        assert SECRET not in serialized
        assert "credentials.invalid" not in serialized
        assert "StackFileContent" not in serialized
        assert "Webhook" not in serialized
        assert "Env" not in serialized
        assert "GitConfig" not in serialized
    assert {method for method, _, _ in port.http.calls} == {"GET"}


@pytest.mark.parametrize("payload", [
    [stack(EndpointId=8)], [stack(EndpointId=None)],
    [stack(Id=True)], [stack(Id="23")], [stack(Name="x\x1b[31m")],
    [stack(Name=" invalid ")], [stack(), stack(Name="duplicate")],
    [stack(Id=index + 1) for index in range(257)],
])
def test_bulk_projection_rejects_cross_endpoint_spoofing_and_malformed_rows(payload):
    with pytest.raises(ValueError):
        project_portainer_stacks(payload, endpoint_id=7, observed_at=NOW)


@pytest.mark.parametrize("bad", [True, 0, -1, "7", 1.5, 1000000001])
def test_invalid_endpoint_is_rejected_before_projection(bad):
    with pytest.raises(ValueError):
        project_portainer_stacks([stack()], endpoint_id=bad, observed_at=NOW)


def test_bulk_status_is_not_runtime_health_or_deployment_proof():
    result = project_portainer_stacks([stack(Status="running")], endpoint_id=7, observed_at=NOW)
    assert result["stacks"][0]["portainer_status_code"] is None
    assert result["stacks"][0]["runtime_health"] == "UNKNOWN"
    assert result["stacks"][0]["deployment_verified"] is False


def test_both_registered_stack_tools_require_capability_system_authorization(tmp_path, monkeypatch):
    state_path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    port = PortainerAdapter("https://example.invalid", "test-key", 7)
    port.http = FakeHttp()
    monkeypatch.setenv("SOFIA_PORTAINER_URL", "https://example.invalid")
    monkeypatch.setenv("SOFIA_PORTAINER_API_KEY", "test-key")
    monkeypatch.setenv("SOFIA_PORTAINER_ENDPOINT_ID", "7")
    monkeypatch.setattr(
        "sofia.modules.integrations.capabilities.PortainerAdapter",
        lambda *args: port,
    )
    tools = create_configured_integration_tools(
        filesystem_root=tmp_path, state_path=state_path,
    )
    by_name = {tool.capability.name: tool for tool in tools}
    for name in ("portainer.stacks", "portainer.stack"):
        assert capability_permission_policy(name).level is PermissionLevel.OBSERVE_READ
        assert name in by_name
        item = by_name[name]
        parameter = {} if name.endswith(".stacks") else {"stack_id": 23}
        request = CapabilityRequest(
            capability=item.capability, parameters=parameter,
            requested_scope=None, rationale="synthetic authorized read",
        )
        denied = CapabilitySystem(lambda _: False)
        denied.register(item.capability, item.handler)
        assert denied.execute(request).kind is CapabilityResultKind.UNAUTHORIZED
        assert port.http.calls == []
        permitted = CapabilitySystem(lambda _: True)
        permitted.register(item.capability, item.handler)
        result = permitted.execute(request)
        assert result.kind is CapabilityResultKind.SUCCESS
        assert SECRET not in json.dumps(result.evidence)
    assert {method for method, _, _ in port.http.calls} == {"GET"}
    assert capability_permission_policy(
        "portainer.container.restart"
    ).level is PermissionLevel.REVERSIBLE_SCOPED
