"""No-network tests for supervised synthetic MENTOR conversations."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sofia.core.mentor.bridge import (
    BridgeConfig, MentorBridgeError, OPENAI_ENDPOINT, OLLAMA_ENDPOINT,
    SCENARIOS, _send_json, run_synthetic_dialogue,
)


class ProviderStub:
    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append((url, payload, headers, timeout))
        if url == OLLAMA_ENDPOINT:
            return {"message": {"role": "assistant", "content": "Hypothesis only; check the listener."}}
        if url == OPENAI_ENDPOINT:
            return {
                "id": "resp_synthetic",
                "status": "completed",
                "model": "gpt-6-luna-2026-10-01",
                "output": [
                    {"type": "reasoning", "summary": []},
                    {"type": "message", "content": [
                        {"type": "output_text", "text": "Good restraint. Test the listener; don't assume."},
                    ]},
                ],
                "usage": {"input_tokens": 140, "output_tokens": 42},
            }
        raise AssertionError("unexpected endpoint")


class TestMentorDialogue(unittest.TestCase):
    def setUp(self):
        self.cfg = BridgeConfig("qwen3.5:9b", "gpt-6-luna")

    def test_two_rounds_alternate_and_bound_api_calls(self):
        stub = ProviderStub()
        result = run_synthetic_dialogue(
            config=self.cfg, scenario_id="service-failure", allow_external=True,
            api_key="test-key-only", sender=stub,
        )
        self.assertEqual(result["rounds"], 2)
        self.assertEqual(len(result["events"]), 4)
        self.assertEqual([c[0] for c in stub.calls],
                         [OLLAMA_ENDPOINT, OPENAI_ENDPOINT] * 2)
        self.assertEqual(result["events"][-1]["speaker"], "external-mentor")
        self.assertEqual(result["events"][1]["usage"]["input_tokens"], 140)
        for _, payload, headers, timeout in stub.calls:
            self.assertNotIn("secret", str(payload).lower())
            self.assertEqual(timeout, 30)
            self.assertEqual(payload["tools"], [])
        for _, payload, headers, _ in stub.calls[1::2]:
            self.assertIs(payload["store"], False)
            self.assertEqual(payload["tool_choice"], "none")
            self.assertEqual(payload["max_output_tokens"], 350)
            self.assertTrue(headers["Authorization"].startswith("Bearer "))
        for _, payload, _, _ in stub.calls[::2]:
            self.assertEqual(payload["stream"], False)
            self.assertEqual(payload["options"]["num_predict"], 350)
            self.assertEqual(payload["messages"][0]["role"], "system")

    def test_no_external_opt_in_makes_no_calls(self):
        stub = ProviderStub()
        with self.assertRaisesRegex(MentorBridgeError, "allow-external"):
            run_synthetic_dialogue(config=self.cfg, scenario_id="service-failure",
                                   allow_external=False, api_key="test-key", sender=stub)
        self.assertFalse(stub.calls)

    def test_unknown_scenario_fails_before_transmitting(self):
        stub = ProviderStub()
        with self.assertRaisesRegex(MentorBridgeError, "synthetic fixtures"):
            run_synthetic_dialogue(config=self.cfg, scenario_id="private-transcript",
                                   allow_external=True, api_key="test-key", sender=stub)
        self.assertFalse(stub.calls)

    def test_no_api_key_fails_before_transmitting(self):
        stub = ProviderStub()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaisesRegex(MentorBridgeError, "API_KEY"):
                run_synthetic_dialogue(
                    config=self.cfg, scenario_id="service-failure",
                    allow_external=True, sender=stub,
                )
        self.assertFalse(stub.calls)

    def test_model_and_round_budget_validation(self):
        for bad in ("/a", "invalid model", "a" * 101, ""):
            with self.assertRaises(MentorBridgeError):
                BridgeConfig("qwen3.5:9b", bad)
        for n in (0, 4, -1):
            with self.assertRaises(MentorBridgeError):
                BridgeConfig("qwen3.5:9b", "gpt-6-luna", max_rounds=n)
        with self.assertRaises(MentorBridgeError):
            BridgeConfig("qwen3.5:9b", "gpt-6-luna", max_output_tokens=1000)

    def test_rejects_unrequested_tool_call_from_ollama(self):
        stub = ProviderStub()
        def bad(url, *args):
            if url == OLLAMA_ENDPOINT:
                return {"message": {"content": "look", "tool_calls": [{"function": {}}]}}
            return stub(url, *args)
        with self.assertRaisesRegex(MentorBridgeError, "tools"):
            run_synthetic_dialogue(config=self.cfg, scenario_id="memory-correction",
                                   allow_external=True, api_key="test-key", sender=bad)
        self.assertFalse(stub.calls)

    def test_rejects_remote_tool_output_even_when_response_completed(self):
        def bad(url, payload, headers, timeout):
            if url == OLLAMA_ENDPOINT:
                return {"message": {"content": "My answer."}}
            return {"status": "completed", "output": [
                {"type": "function_call", "name": "execute", "arguments": "{}"},
            ]}
        with self.assertRaisesRegex(MentorBridgeError, "no tools"):
            run_synthetic_dialogue(config=self.cfg, scenario_id="screen-understanding",
                                   allow_external=True, api_key="test-key", sender=bad)

    def test_rejects_secret_like_local_output_before_external_call(self):
        called = []
        def bad(url, payload, headers, timeout):
            called.append(url)
            return {"message": {"content": "sk-" + "A" * 35}}
        with self.assertRaisesRegex(MentorBridgeError, "secret"):
            run_synthetic_dialogue(config=self.cfg, scenario_id="service-failure",
                                   allow_external=True, api_key="test-key", sender=bad)
        self.assertEqual(called, [OLLAMA_ENDPOINT])

    def test_rejects_empty_and_incomplete_provider_output(self):
        for response in (
            {"status": "incomplete", "output": []},
            {"status": "completed", "output": []},
            {"status": "completed", "output": [
                {"type": "message", "content": [{"type": "refusal", "refusal": "No"}]},
            ]},
        ):
            def bad(url, payload, headers, timeout):
                return {"message": {"content": "Local answer"}} if url == OLLAMA_ENDPOINT else response
            with self.assertRaises(MentorBridgeError):
                run_synthetic_dialogue(config=self.cfg, scenario_id="service-failure",
                                       allow_external=True, api_key="test-key", sender=bad)

    def test_cli_preview_cannot_call_either_provider(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from sofia.core.mentor.__main__ import main
        stream = StringIO()
        with patch("sofia.core.mentor.__main__.run_synthetic_dialogue",
                   side_effect=AssertionError("must never transmit")):
            with redirect_stdout(stream):
                result = main([
                    "converse", "--scenario", "service-failure",
                    "--local-model", "qwen3.5:9b",
                    "--external-model", "gpt-6-luna", "--preview",
                ])
        self.assertEqual(result, 0)
        self.assertIn("synthetic-preview-no-network", stream.getvalue())
        self.assertIn("ECONNREFUSED", stream.getvalue())

    def test_fixed_only_endpoint_rejects_other_urls(self):
        with self.assertRaisesRegex(MentorBridgeError, "allowlist"):
            _send_json("https://evil.example.com/data", {}, {}, 10)


if __name__ == "__main__":
    unittest.main()
