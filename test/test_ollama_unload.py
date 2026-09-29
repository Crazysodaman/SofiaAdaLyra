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
