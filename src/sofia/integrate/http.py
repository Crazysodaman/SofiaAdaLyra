"""Small injectable JSON HTTP client for typed service adapters."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class JsonHttpResponse:
    status: int
    payload: Any
    headers: Mapping[str, str]


class JsonHttpError(RuntimeError):
    pass


class JsonHttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: Any = None,
        timeout: float = 10.0,
    ) -> JsonHttpResponse: ...


class UrllibJsonHttpClient:
    """Dependency-free JSON client. Endpoint authority is owned by adapter config."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: Any = None,
        timeout: float = 10.0,
    ) -> JsonHttpResponse:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("integration URL must be absolute http/https")
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout must be positive")

        body = None
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(dict(headers))
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        request = Request(
            url=url,
            data=body,
            headers=request_headers,
            method=method.upper(),
        )
        try:
            with urlopen(request, timeout=float(timeout)) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
                decoded: Any = None
                if raw:
                    if "json" in content_type.lower():
                        decoded = json.loads(raw.decode("utf-8"))
                    else:
                        text = raw.decode("utf-8", errors="replace")
                        try:
                            decoded = json.loads(text)
                        except json.JSONDecodeError:
                            decoded = text
                return JsonHttpResponse(
                    status=int(response.status),
                    payload=decoded,
                    headers=dict(response.headers.items()),
                )
        except HTTPError as exc:
            raw = exc.read()
            detail = raw.decode("utf-8", errors="replace") if raw else str(exc)
            raise JsonHttpError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise JsonHttpError(f"HTTP transport failed: {exc.reason}") from exc
