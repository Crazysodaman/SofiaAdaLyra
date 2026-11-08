"""Read-only Portainer stack projection uses exactly the selected environment."""
import pytest

from sofia.modules.integrations.portainer import PortainerAdapter

STACK = {
    "Id": 19, "EndpointId": 7, "Name": "mealie", "Type": 2,
    "Status": 1, "GitConfig": {"Password": "must-never-leak"},
    "Env": [{"name": "PASSWORD", "value": "also-must-never-leak"}],
}


class FakeHttp:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.response


def adapter(response):
    port = PortainerAdapter("https://example.invalid:9443", "not-a-real-secret", 7)
    port.http = FakeHttp(response)
    return port


def test_stack_summary_uses_read_only_endpoint_and_redacts_all_secrets():
    port = adapter(STACK)
    result = port.stack_summary(19)
    assert port.http.calls == [("GET", "/api/stacks/19", {})]
    assert result["name"] == "mealie"
    assert result["runtime_health_verified"] is False
    assert "must-never-leak" not in str(result)
    assert result["source_class"] == "git"


@pytest.mark.parametrize("stack_id", [0, -1, True, "19", 1.5])
def test_stack_summary_never_sends_invalid_stack_id(stack_id):
    port = adapter(STACK)
    with pytest.raises(ValueError):
        port.stack_summary(stack_id)
    assert port.http.calls == []


def test_stack_summary_rejects_different_environment_or_spoofed_response():
    for changed in ({"EndpointId": 8}, {"Id": 20}, {"EndpointId": None}):
        port = adapter(STACK | changed)
        with pytest.raises(ValueError):
            port.stack_summary(19)
