"""Narrow National Weather Service REST adapter.

Transport is pinned to HTTPS api.weather.gov. This adapter does not expose
arbitrary HTTP and does not provide browser/search authority.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .http import ServiceHTTPError


NWS_API_BASE = "https://api.weather.gov"
NWS_API_HOST = "api.weather.gov"


def validate_nws_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("NWS URL/path must be nonempty")
    url = urljoin(NWS_API_BASE + "/", value.strip())
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != NWS_API_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise ValueError(
            "NWS adapter may contact only https://api.weather.gov"
        )
    return url


class _NwsRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        validate_nws_url(newurl)
        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )


class NwsAdapter:
    """Read-only JSON adapter pinned to the official NWS API host."""

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 10.0,
    ) -> None:
        if (
            not isinstance(user_agent, str)
            or not user_agent.strip()
        ):
            raise ValueError("NWS User-Agent is required")
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("NWS timeout must be positive")
        self.user_agent = user_agent.strip()
        self.timeout = float(timeout)
        self._opener = build_opener(_NwsRedirectHandler())

    @staticmethod
    def normalize_url(path_or_url: str) -> str:
        return validate_nws_url(path_or_url)

    def get(self, path_or_url: str) -> dict[str, Any]:
        url = self.normalize_url(path_or_url)
        request = Request(
            url,
            headers={
                "Accept": "application/geo+json",
                "User-Agent": self.user_agent,
            },
            method="GET",
        )
        try:
            with self._opener.open(
                request,
                timeout=self.timeout,
            ) as response:
                raw = response.read()
        except HTTPError as exc:
            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
            raise ServiceHTTPError(
                f"NWS HTTP {exc.code}: {body[:500]}"
            ) from exc
        except URLError as exc:
            raise ServiceHTTPError(
                f"NWS request failed: {exc.reason}"
            ) from exc

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ServiceHTTPError(
                "NWS returned non-JSON data"
            ) from exc
        if not isinstance(data, dict):
            raise ServiceHTTPError(
                "NWS returned an invalid JSON document"
            )
        return data
