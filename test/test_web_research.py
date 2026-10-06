from datetime import timezone
import json
import sqlite3

import pytest

from sofia.net import HTTPExchange, PublicHTTPSClient, WebResearchService


def response(body=b"ok", *, status=200, content_type="text/plain", **headers):
    return HTTPExchange(
        status=status,
        headers={"content-type": content_type, **headers},
        body=body,
    )


@pytest.mark.parametrize("url", [
    "http://example.com/", "https://user:pass@example.com/",
    "https://localhost/", "https://thing.local/", "https://example.com:8443/",
])
def test_public_client_rejects_unsafe_urls(url):
    client = PublicHTTPSClient(
        resolver=lambda host, port: ("93.184.216.34",),
        exchange=lambda *args: response(),
    )
    with pytest.raises((ValueError, PermissionError)):
        client.request(url)


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "fd00::1",
])
def test_public_client_rejects_non_public_dns(address):
    client = PublicHTTPSClient(
        resolver=lambda host, port: (address,),
        exchange=lambda *args: response(),
    )
    with pytest.raises(PermissionError, match="non-public"):
        client.request("https://example.com/")


def test_redirect_is_revalidated_and_dns_is_pinned():
    calls = []

    def exchange(host, address, port, target, headers, max_bytes):
        calls.append((host, address, target, headers["Host"]))
        if host == "example.com":
            return response(status=302, location="https://iana.org/final")
        return response(b"done")

    client = PublicHTTPSClient(
        resolver=lambda host, port: {
            "example.com": ("93.184.216.34",),
            "iana.org": ("192.0.43.8",),
        }[host],
        exchange=exchange,
    )
    final_url, result = client.request("https://example.com/start")
    assert final_url == "https://iana.org/final"
    assert result.body == b"done"
    assert calls == [
        ("example.com", "93.184.216.34", "/start", "example.com"),
        ("iana.org", "192.0.43.8", "/final", "iana.org"),
    ]


def test_fetch_strips_active_html_and_persists_metadata_only(tmp_path):
    body = b"<title>Example</title><script>steal secrets</script><p>Hello world</p>"
    service = WebResearchService(
        tmp_path / "state.db",
        client=PublicHTTPSClient(
            resolver=lambda host, port: ("93.184.216.34",),
            exchange=lambda *args: response(body, content_type="text/html"),
        ),
    )
    result = service.fetch("https://example.com/private/path?q=secret")
    assert result.title == "Example"
    assert "Hello world" in result.text
    assert "steal secrets" not in result.text
    assert result.tool_payload()["trust"] == "external_untrusted_content"
    with sqlite3.connect(tmp_path / "state.db") as db:
        row = db.execute(
            "SELECT target_host,status,target_path_sha256 FROM net_web_evidence"
        ).fetchone()
        schema = db.execute(
            "SELECT sql FROM sqlite_master WHERE name='net_web_evidence'"
        ).fetchone()[0]
    assert row[:2] == ("example.com", "success")
    assert "secret" not in row[2]
    assert "content" not in schema.casefold()


def test_wikipedia_search_is_bounded_untrusted_evidence(tmp_path):
    payload = json.dumps({"query": {"search": [{
        "title": "Fox", "snippet": "A <b>fox</b> is an animal",
    }]}}).encode()
    service = WebResearchService(
        tmp_path / "state.db",
        client=PublicHTTPSClient(
            resolver=lambda host, port: ("208.80.154.224",),
            exchange=lambda *args: response(payload, content_type="application/json"),
        ),
    )
    result = service.search("fox intelligence")
    assert result.observed_at.tzinfo is timezone.utc
    assert result.items[0].url == "https://en.wikipedia.org/wiki/Fox"
    assert result.tool_payload()["trust"] == "external_untrusted_content"


def test_search_failure_is_recorded_without_raw_query(tmp_path):
    service = WebResearchService(
        tmp_path / "state.db",
        client=PublicHTTPSClient(
            resolver=lambda host, port: ("208.80.154.224",),
            exchange=lambda *args: (_ for _ in ()).throw(OSError("offline")),
        ),
    )
    with pytest.raises(OSError):
        service.search("a private question")
    with sqlite3.connect(tmp_path / "state.db") as db:
        row = db.execute(
            "SELECT status,query_sha256,error_kind FROM net_web_evidence"
        ).fetchone()
    assert row[0] == "failed"
    assert row[1] != "a private question"
    assert row[2] == "OSError"
