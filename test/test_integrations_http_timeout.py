from urllib.error import URLError

import pytest

import sofia.modules.integrations.http as http_module
from sofia.modules.integrations.http import JsonHttpClient, ServiceHTTPError


class Response:
    def __enter__(self):
        return self
    def __exit__(self,*_):
        return False
    def read(self, size=None):
        body = b'{"ok":true}'
        return body if size is None else body[:size]


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


def test_read_only_json_metadata_has_hard_response_byte_ceiling(monkeypatch):
    observed=[]
    class SizedResponse:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self,size=None):
            observed.append(size)
            return b"x" * size

    monkeypatch.setattr(
        http_module,"urlopen",
        lambda *_a,**_k: SizedResponse(),
    )
    with pytest.raises(ServiceHTTPError,match="exceeded max_bytes"):
        JsonHttpClient("http://127.0.0.1:11434").request(
            "POST","/api/show",payload={"name":"approved:1b"},max_bytes=1024,
        )
    assert observed == [1025]

    with pytest.raises(ValueError,match="max_bytes"):
        JsonHttpClient("http://127.0.0.1:11434").request(
            "GET","/api/tags",max_bytes=4 * 1024 * 1024 + 1,
        )


def test_request_json_is_bounded_even_without_explicit_limit(monkeypatch):
    sizes = []

    class UnboundedPeer(Response):
        def read(self, size=None):
            sizes.append(size)
            return b"x" * size

    monkeypatch.setattr(
        http_module, "urlopen",
        lambda request, timeout: UnboundedPeer(),
    )

    with pytest.raises(ServiceHTTPError, match="exceeded max_bytes"):
        JsonHttpClient("http://127.0.0.1:11434").request("GET", "/api/tags")

    assert sizes == [4 * 1024 * 1024 + 1]


def test_http_error_body_is_also_bounded(monkeypatch):
    from urllib.error import HTTPError

    sizes = []

    class LargeErrorBody:
        def read(self, size=None):
            sizes.append(size)
            return b"s" * size
        def close(self):
            pass

    def fail(request, timeout):
        raise HTTPError(
            "https://example.invalid/test", 500, "synthetic",
            hdrs={}, fp=LargeErrorBody(),
        )

    monkeypatch.setattr(http_module, "urlopen", fail)

    with pytest.raises(ServiceHTTPError, match="HTTP 500"):
        JsonHttpClient("https://example.invalid").request("GET", "/test")

    assert sizes == [501]


def test_json_request_does_not_accept_none_as_unlimited_response_cap(monkeypatch):
    monkeypatch.setattr(
        http_module, "urlopen",
        lambda *args, **kwargs: pytest.fail("unbounded request must not start"),
    )
    with pytest.raises(ValueError, match="max_bytes"):
        JsonHttpClient("http://127.0.0.1:11434").request(
            "GET", "/api/tags", max_bytes=None,
        )
