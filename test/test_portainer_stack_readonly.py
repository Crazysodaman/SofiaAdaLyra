"""Portainer stack details are GET-only, exact-scoped, secret-free observations."""
import pytest

from sofia.modules.integrations.portainer import PortainerAdapter


STACK = {
    "Id": 19, "EndpointId": 7, "Name": "mealie", "Status": 1,
    "GitConfig": {"Password": "must-never-leak"},
    "Env": [{"name": "PASSWORD", "value": "also-must-never-leak"}],
    "StackFileContent": "password: compose-secret",
}


class FakeHttp:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.response


def adapter(response):
    port = PortainerAdapter("https://example.invalid:9443", "fake-test-key", 7)
    port.http = FakeHttp(response)
    return port


def test_stack_metadata_uses_get_and_never_returns_credentials():
    port = adapter(STACK)
    result = port.stack_summary(19)
    assert port.http.calls == [("GET", "/api/stacks/19", {})]
    assert result["name"] == "mealie"
    assert result["source_hint"] == "git"
    assert result["evidence_class"] == "portainer_metadata_unverified_health"
    assert "must-never-leak" not in str(result)
    assert "compose-secret" not in str(result)


@pytest.mark.parametrize("stack_id", [0, -1, True, "19", 1.5])
def test_invalid_id_never_sends_request(stack_id):
    port = adapter(STACK)
    with pytest.raises(ValueError):
        port.stack_summary(stack_id)
    assert port.http.calls == []


def test_different_environment_and_spoofed_stack_fail_closed():
    for changed in ({"EndpointId": 8}, {"Id": 20}, {"EndpointId": None}):
        port = adapter(STACK | changed)
        with pytest.raises(ValueError):
            port.stack_summary(19)


def test_no_health_claim_on_incomplete_metadata():
    port = adapter({
        "Id": 19, "EndpointId": 7, "Name": "mealie",
        "Status": 1, "GitConfig": None,
    })
    result = port.stack_summary(19)
    assert result["source_hint"] == "unknown"
    assert "healthy" not in str(result).lower()
