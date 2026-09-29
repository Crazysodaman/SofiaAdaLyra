from urllib.error import URLError

import pytest

import sofia.integrations.http as http_module
from sofia.integrations.http import JsonHttpClient, ServiceHTTPError


class Response:
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def read(self):
        return b'{"ok":true}'


def test_request_uses_per_call_timeout_override(monkeypatch):
    observed={}
    def fake_urlopen(request,timeout):
        observed["timeout"]=timeout
        return Response()
    monkeypatch.setattr(http_module,"urlopen",fake_urlopen)

    result=JsonHttpClient(
        "http://127.0.0.1:11434",
        timeout=10,
    ).request("GET","/api/tags",timeout=123)

    assert result=={"ok":True}
    assert observed["timeout"]==123.0


def test_request_normalizes_raw_timeout_error(monkeypatch):
    def fake_urlopen(request,timeout):
        raise TimeoutError("synthetic")
    monkeypatch.setattr(http_module,"urlopen",fake_urlopen)

    with pytest.raises(ServiceHTTPError,match="timed out"):
        JsonHttpClient(
            "http://127.0.0.1:11434",
        ).request("GET","/api/tags")


def test_request_rejects_invalid_override_timeout(monkeypatch):
    monkeypatch.setattr(
        http_module,
        "urlopen",
        lambda *_args,**_kwargs:pytest.fail("network called"),
    )

    with pytest.raises(ValueError,match="timeout"):
        JsonHttpClient(
            "http://127.0.0.1:11434",
        ).request("GET","/api/tags",timeout=0)
