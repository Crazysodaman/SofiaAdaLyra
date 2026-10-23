"""Provider HTTP diagnostic tests use fake responses and never contact OpenAI."""
from __future__ import annotations

from io import BytesIO, StringIO
import json
import os
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch
from urllib import error

from sofia.core.mentor.__main__ import main
from sofia.core.mentor.bridge import _send_json, OPENAI_ENDPOINT, MentorBridgeError
from sofia.core.mentor.openai_diagnostics import (
    MODELS_ENDPOINT, check_openai_model, openai_http_error,
)


def http_error(status, error_obj):
    body = json.dumps({"error": error_obj}).encode("utf-8")
    return error.HTTPError(
        "https://api.openai.com/v1/responses", status,
        "FAKE-SENSITIVE-REASON-sk-FAKE-KEY-123456789012345", {},
        BytesIO(body),
    )


class FakeResponse:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *unused):
        return False
    def read(self, amount):
        return self.data[:amount]


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.calls = []
    def open(self, req, timeout):
        self.calls.append((req, timeout))
        return FakeResponse(self.data)


class TestSafeOpenAIErrors(TestCase):
    def test_429_extracts_only_sanitized_quota_code(self):
        exc = http_error(429, {
            "code": "credit_balance_exhausted", "type": "insufficient_quota",
            "message": "Sensitive sk-VERYSECRET1234567890 and private user prompt!",
        })
        result = openai_http_error(exc)
        self.assertIn("HTTP 429", result)
        self.assertIn("code=credit_balance_exhausted", result)
        self.assertIn("Add credits", result)
        self.assertNotIn("VERYSECRET", result)
        self.assertNotIn("private user prompt", result)
        self.assertNotIn("FAKE-SENSITIVE-REASON", result)

    def test_invalid_request_parameter_can_be_diagnosed_without_body(self):
        result = openai_http_error(http_error(400, {
            "code": "invalid_request_error", "param": "tool_choice",
            "message": "your secret request contents",
        }))
        self.assertIn("HTTP 400", result)
        self.assertIn("param=tool_choice", result)
        self.assertNotIn("your secret", result)

    def test_malicious_error_fields_are_not_echoed(self):
        result = openai_http_error(http_error(401, {
            "code": "foo\nAuthorization: Bearer secret",
            "type": {"a": "not string"},
            "param": "field\napi-key",
            "message": "secret",
        }))
        self.assertIn("HTTP 401", result)
        self.assertNotIn("Authorization", result)
        self.assertNotIn("api-key", result)
        self.assertNotIn("secret", result)

    def test_bridge_uses_safe_diagnostics_for_http_errors(self):
        exc = http_error(429, {
            "code": "project_spend_limit_exceeded",
            "message": "private prompt and secret",
        })
        class FailingOpener:
            def open(self, req, timeout):
                raise exc
        with patch("sofia.core.mentor.bridge.request.build_opener",
                   return_value=FailingOpener()):
            with self.assertRaises(MentorBridgeError) as caught:
                _send_json(OPENAI_ENDPOINT, {
                    "model": "gpt-6-luna",
                }, {
                    "Content-Type": "application/json", "Authorization": "Bearer fake",
                }, 10)
        message = str(caught.exception)
        self.assertIn("HTTP 429", message)
        self.assertIn("project_spend_limit_exceeded", message)
        self.assertNotIn("private prompt", message)
        self.assertNotIn("Bearer fake", message)

    def test_preflight_is_get_only_and_does_not_send_private_content(self):
        opener = FakeOpener(json.dumps({
            "object": "model", "id": "gpt-6-luna", "owned_by": "openai"
        }).encode())
        result = check_openai_model(
            "gpt-6-luna", "fake-secret", opener_factory=lambda: opener,
        )
        self.assertTrue(result["metadata_available"])
        self.assertFalse(result["response_generation_tested"])
        self.assertEqual(len(opener.calls), 1)
        req, timeout = opener.calls[0]
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, MODELS_ENDPOINT + "gpt-6-luna")
        self.assertIsNone(req.data)
        self.assertEqual(req.get_header("Authorization"), "Bearer fake-secret")
        self.assertEqual(timeout, 15)
        self.assertNotIn("fake-secret", repr(result))

    def test_preflight_rejects_untrusted_path_before_network(self):
        for invalid in ("../secret", "gpt-6-luna?key=secret", "gpt:6", ""):
            with self.assertRaises(ValueError):
                check_openai_model(
                    invalid, "valid-placeholder",
                    opener_factory=lambda: self.fail("network used"),
                )

    def test_no_opt_in_preflight_never_calls_network(self):
        with patch("sofia.core.mentor.__main__.check_openai_model",
                   side_effect=AssertionError("network must not be used")):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-secret"}):
                self.assertEqual(main(["check-api", "--external-model", "gpt-6-luna"]), 2)

    def test_cli_preflight_prints_safe_metadata_not_key(self):
        with patch("sofia.core.mentor.__main__.check_openai_model",
                   return_value={"model": "gpt-6-luna", "metadata_available": True}):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "never-print-this"}):
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main([
                        "check-api", "--external-model", "gpt-6-luna",
                        "--allow-external",
                    ]), 0)
                self.assertIn("metadata_available", output.getvalue())
                self.assertNotIn("never-print-this", output.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
