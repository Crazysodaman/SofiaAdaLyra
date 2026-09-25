import pytest

from sofia.external.model import ExternalSystemAction
from sofia.integrate.adapters import HomeAssistantAdapter
from sofia.integrate.http import JsonHttpResponse

class FakeHttp:
    def __init__(self,responses):
        self.responses=list(responses); self.calls=[]
    def request(self,method,url,*,headers=None,payload=None,timeout=10.0):
        self.calls.append((method,url,headers,payload))
        return self.responses.pop(0)

def test_home_assistant_typed_observe_and_service_call():
    http=FakeHttp([
        JsonHttpResponse(200,{"message":"API running."},{}),
        JsonHttpResponse(200,[{"entity_id":"light.lab","state":"on"}],{}),
        JsonHttpResponse(200,[],{}),
    ])
    adapter=HomeAssistantAdapter("http://ha.local:8123","token-value",http=http)
    assert adapter.observe().evidence["entity_count"]==1
    result=adapter.execute_action(ExternalSystemAction(
        adapter.system.system_id,
        "call_service",
        {"domain":"light","service":"turn_off","data":{"entity_id":"light.lab"}},
    ))
    assert result.evidence["status"]==200
    assert http.calls[-1][1].endswith("/api/services/light/turn_off")

def test_home_assistant_rejects_invalid_service_path():
    adapter=HomeAssistantAdapter("http://ha.local:8123","token-value",http=FakeHttp([]))
    with pytest.raises(ValueError):
        adapter.execute_action(ExternalSystemAction(
            adapter.system.system_id,
            "call_service",
            {"domain":"invalid/path","service":"turn_on","data":{}},
        ))
