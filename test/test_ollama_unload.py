from sofia.integrations.ollama import OllamaAdapter


class Http:
    def __init__(self):
        self.calls=[]
    def request(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        return {"done":True}


def test_unload_uses_keep_alive_zero_without_stopping_service():
    adapter=object.__new__(OllamaAdapter)
    adapter.http=Http()
    result=adapter.unload("qwen3:14b")
    assert result=={"done":True}
    args,kwargs=adapter.http.calls[0]
    assert args==("POST","/api/generate")
    assert kwargs["payload"]["model"]=="qwen3:14b"
    assert kwargs["payload"]["keep_alive"]==0
    assert kwargs["payload"]["stream"] is False
    assert kwargs["timeout"]==60.0



def test_load_uses_configured_keep_alive_without_generating_text():
    adapter=object.__new__(OllamaAdapter)
    adapter.http=Http()
    result=adapter.load("vendor/custom:9b", keep_alive="7m")
    assert result=={"done":True}
    args,kwargs=adapter.http.calls[0]
    assert args==("POST","/api/generate")
    assert kwargs["payload"]=={
        "model":"vendor/custom:9b",
        "keep_alive":"7m",
        "prompt":"",
        "stream":False,
    }
    assert kwargs["timeout"]==600.0


def test_metadata_inventory_calls_are_bounded_read_only_http():
    adapter=object.__new__(OllamaAdapter)
    adapter.http=Http()
    adapter.models()
    adapter.version()
    adapter.show("approved:1b")
    assert adapter.http.calls == [
        (("GET","/api/tags"), {"max_bytes":1_048_576}),
        (("GET","/api/version"), {"max_bytes":65_536}),
        (("POST","/api/show"), {
            "payload":{"name":"approved:1b"},
            "max_bytes":2_097_152,
        }),
    ]
