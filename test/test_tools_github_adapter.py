from sofia.external.model import ExternalSystemAction
from sofia.integrate.adapters import GitHubRepositoryAdapter
from sofia.integrate.http import JsonHttpResponse

class FakeHttp:
    def __init__(self,responses):
        self.responses=list(responses); self.calls=[]
    def request(self,method,url,*,headers=None,payload=None,timeout=10.0):
        self.calls.append((method,url,headers,payload))
        return self.responses.pop(0)

def test_github_repository_observe_and_issue_create():
    http=FakeHttp([
        JsonHttpResponse(200,{"full_name":"Crazysodaman/SofiaAdaLyra"},{}),
        JsonHttpResponse(200,[{"number":103}],{}),
        JsonHttpResponse(201,{"number":104},{}),
    ])
    adapter=GitHubRepositoryAdapter("Crazysodaman","SofiaAdaLyra","token-value",http=http)
    assert adapter.observe().evidence["open_pull_request_count"]==1
    result=adapter.execute_action(ExternalSystemAction(
        adapter.system.system_id,
        "create_issue",
        {"title":"tool test","body":"evidence"},
    ))
    assert result.evidence["issue"]["number"]==104
    assert http.calls[-1][1].endswith("/repos/Crazysodaman/SofiaAdaLyra/issues")
