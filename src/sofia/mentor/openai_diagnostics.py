"""Safe, no-inference OpenAI API preflight and HTTP error classification.

Never display arbitrary API error messages, request headers, credentials, or
response bodies. Only an allowlisted status, a conservative error code and
known parameter names are shown. No private Sofía state is read or sent.
"""
from __future__ import annotations

import json
import re
from urllib import error, request

MODELS_ENDPOINT = "https://api.openai.com/v1/models/"
MODEL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{1,99}\Z")
ERROR_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,79}\Z")
MAX_ERROR_BYTES = 4096

_STATUS_HELP = {
    400: "Request was rejected. Inspect the sanitized parameter name and bridge request schema.",
    401: "Check API key validity, project membership and any IP access restrictions.",
    402: "Check your API project's billing configuration.",
    403: "The project, account, or region may lack access. Check API permissions.",
    404: "Check that the model is available to this API project and that the endpoint is valid.",
    408: "The request timed out. Check network connectivity and retry later.",
    409: "The request conflicts with current API state. Do not blindly retry.",
    429: "Check API credit balance, project and organization spend limits, and rate limits.",
    500: "Provider-side error. Check service status before a bounded retry.",
    502: "Provider gateway error. Check service status.",
    503: "Provider temporarily unavailable or overloaded. Retry after the advised interval.",
    504: "Gateway timed out. Retry cautiously.",
}
_CODE_HELP = {
    "credit_balance_exhausted": "Add credits in API billing; repeating requests will not fix this.",
    "insufficient_quota": "Check API credits and spend limits; ChatGPT subscription is separate.",
    "project_spend_limit_exceeded": "Review this API project's enforced spending limit.",
    "organization_spend_limit_exceeded": "Review organization-level API spending limit.",
    "organization_usage_limit_exceeded": "Review your API organization usage allocation.",
    "model_not_found": "Verify this model is accessible to the API project.",
    "invalid_api_key": "Create/check an API project key; never paste it into chat.",
    "invalid_request_error": "Inspect sanitized param and request schema; do not expose raw error message.",
    "rate_limit_exceeded": "Reduce call rate; do not loop retries.",
    "server_is_overloaded": "Try later; do not immediately retry repeatedly.",
}
def _safe_field(value: object) -> str | None:
    return value if isinstance(value, str) and ERROR_FIELD.fullmatch(value) else None


def openai_http_error(exc: error.HTTPError) -> str:
    """Return only safe, diagnosis-relevant fields from an HTTP failure."""
    status = exc.code if type(exc.code) is int and 400 <= exc.code <= 599 else 0
    code = param = None
    try:
        raw = exc.read(MAX_ERROR_BYTES + 1)
        if len(raw) <= MAX_ERROR_BYTES:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                detail = parsed.get("error")
                if isinstance(detail, dict):
                    code = _safe_field(detail.get("code")) or _safe_field(detail.get("type"))
                    param = _safe_field(detail.get("param"))
    except (OSError, ValueError, UnicodeDecodeError, TypeError):
        pass
    hint = _CODE_HELP.get(code) or _STATUS_HELP.get(
        status, "Check OpenAI API dashboard for access or service status."
    )
    parts = [f"OpenAI HTTP {status or 'unknown'}"]
    if code:
        parts.append("code=" + code)
    if param:
        parts.append("param=" + param)
    return " ".join(parts) + ". " + hint


def _opener():
    class NoRedirects(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise RuntimeError("OpenAI diagnostics reject HTTP redirects")
    return request.build_opener(request.ProxyHandler({}), NoRedirects())


def check_openai_model(
    model: str, key: str, *, opener_factory=None, timeout: int = 15,
) -> dict:
    """Query GET /v1/models/{id}; no inference, private data, or billed generation.

    A successful metadata response confirms the key can retrieve the model,
    but does NOT prove that this project can successfully create a response.
    """
    if not isinstance(model, str) or MODEL_ID.fullmatch(model) is None:
        raise ValueError("invalid OpenAI model identifier")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("OPENAI_API_KEY is missing")
    if type(timeout) is not int or not 5 <= timeout <= 30:
        raise ValueError("timeout out of bounds")
    req = request.Request(
        MODELS_ENDPOINT + model,
        method="GET",
        headers={"Authorization": "Bearer " + key.strip()},
    )
    opener = _opener() if opener_factory is None else opener_factory()
    try:
        with opener.open(req, timeout=timeout) as response:
            payload = response.read(4097)
    except error.HTTPError as exc:
        raise RuntimeError(openai_http_error(exc)) from None
    except (error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("OpenAI metadata check failed: " + type(exc).__name__) from None
    if len(payload) > 4096:
        raise RuntimeError("OpenAI metadata response is unexpectedly large")
    try:
        item = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("Invalid OpenAI metadata JSON") from None
    if not isinstance(item, dict) or item.get("id") != model or item.get("object") != "model":
        raise RuntimeError("OpenAI returned unexpected model metadata")
    return {
        "model": model,
        "metadata_available": True,
        "response_generation_tested": False,
        "explanation": (
            "Metadata access worked; a Responses API request may still be denied "
            "by billing, project permissions, quotas or request parameters."
        ),
    }
