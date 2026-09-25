from sofia.external.model import ExternalSystemAction
from sofia.integrate.adapters import PortainerAdapter
from sofia.integrate.http import JsonHttpResponse

class FakeHttp:
    def __init__(self,responses):
        self.responses=list(responses); self.calls=[]
    def request(self,method,url,*,headers=None,payload=None,timeout=10.0):
        self.calls.append((method,url,headers,payload))
        return self.responses.pop(0)

def test_portainer_observe_and_container_restart():
    http=FakeHttp([
        JsonHttpResponse(200,[{"Id":1,"Name":"eos"}],{}),
        JsonHttpResponse(204,None,{}),
    ])
    adapter=PortainerAdapter("https://portainer.local","key-value",http=http)
    assert adapter.observe().evidence["endpoint_count"]==1
    result=adapter.execute_action(ExternalSystemAction(
        adapter.system.system_id,
        "restart_container",
        {"endpoint_id":1,"container_id":"abc123"},
    ))
    assert result.evidence["operation"]=="restart"
    assert http.calls[-1][1].endswith("/api/endpoints/1/docker/containers/abc123/restart")
