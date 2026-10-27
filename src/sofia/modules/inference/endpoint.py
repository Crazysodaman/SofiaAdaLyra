"""Validated Platform-owned endpoint selection for the Ollama provider.

Both inference and lifecycle adapters resolve their endpoint through this
module.  Keeping the environment boundary here prevents a provider from
silently using the Ollama client's loopback default while inventory is read
from a different service.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit


DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
OLLAMA_ENDPOINT_ENVIRONMENT_KEY = "SOFIA_OLLAMA_URL"


def validate_ollama_endpoint(value: str) -> str:
    """Return a canonical HTTP(S) origin or reject an unsafe endpoint."""
    if not isinstance(value, str):
        raise TypeError("Ollama endpoint must be text")
    candidate = value.strip()
    if not candidate or len(candidate) > 2048 or any(
        character in candidate for character in "\r\n\x00"
    ):
        raise ValueError("Ollama endpoint must be bounded nonempty text")
    parsed = urlsplit(candidate)
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise ValueError("Ollama endpoint must use HTTP or HTTPS")
    if not parsed.hostname:
        raise ValueError("Ollama endpoint requires a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Ollama endpoint must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Ollama endpoint must be an origin without path or query")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Ollama endpoint port is invalid") from exc
    host = parsed.hostname.casefold()
    if ":" in host:
        host = f"[{host}]"
    netloc = host if port is None else f"{host}:{port}"
    return urlunsplit((parsed.scheme.casefold(), netloc, "", "", ""))


def configured_ollama_endpoint(
    environment: Mapping[str, str] | None = None,
) -> str:
    """Resolve the one local endpoint setting inherited by worker processes."""
    values = os.environ if environment is None else environment
    return validate_ollama_endpoint(
        values.get(OLLAMA_ENDPOINT_ENVIRONMENT_KEY, DEFAULT_OLLAMA_ENDPOINT)
    )
