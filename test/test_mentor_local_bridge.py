"""Local MENTOR transport must never depend on API credits or cloud calls."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

from sofia.mentor import MentorAuditError
from sofia.mentor.__main__ import main
from sofia.mentor.bridge import MentorBridgeError, OLLAMA_ENDPOINT
from sofia.mentor.local_bridge import LocalBridgeConfig, run_local_dialogue


class LocalOllamaStub:
    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append((url, payload, headers, timeout))
        if payload["model"] == "qwen3.5:9b":
            answer = "Observed: ECONNREFUSED and disabled listener. Check bound port."
        else:
            answer = "Separate observation from hypothesis. Verify listener state."
        return {
            "model": payload["model"], "done": True,
            "message": {"role": "assistant", "content": answer},
            "prompt_eval_count": 60, "eval_count": 30,
        }


class TestLocalMentor(TestCase):
    def setUp(self):
        self.cfg = LocalBridgeConfig("qwen3.5:9b", "qwen3:14b")

    def test_two_models_sequential_no_cloud_and_unload_each_response(self):
        sender = LocalOllamaStub()
        response = run_local_dialogue(
            config=self.cfg, scenario_id="service-failure", sender=sender
        )
        self.assertEqual(response["rounds"], 2)
        self.assertEqual(response["mode"], "local-ollama-only-no-cloud")
        self.assertFalse(response["safety"]["cloud_data_transfer"])
        self.assertEqual(response["safety"]["openai_api_calls"], 0)
        self.assertEqual([e["speaker"] for e in response["events"]],
                         ["local-student", "local-mentor"] * 2)
        self.assertEqual([c[1]["model"] for c in sender.calls],
                         ["qwen3.5:9b", "qwen3:14b"] * 2)
        for url, payload, headers, timeout in sender.calls:
            self.assertEqual(url, OLLAMA_ENDPOINT)
            self.assertFalse(payload["think"])
            self.assertFalse(payload["stream"])
            self.assertEqual(payload["keep_alive"], 0)
            self.assertEqual(payload["tools"], [])
            self.assertEqual(payload["options"]["num_ctx"], 2048)
            self.assertEqual(timeout, 60)
            self.assertNotIn("Authorization", headers)

    def test_later_student_round_receives_critic_feedback_as_untrusted(self):
        sender = LocalOllamaStub()
        run_local_dialogue(
            config=self.cfg, scenario_id="memory-correction", sender=sender,
        )
        prompt = sender.calls[2][1]["messages"][-1]["content"]
        self.assertIn("different untrusted local model", prompt)
        self.assertIn("Verify listener state", prompt)

    def test_local_only_even_if_openai_key_set(self):
        sender = LocalOllamaStub()
        with patch.dict("os.environ", {"OPENAI_API_KEY": "DO-NOT-TRANSMIT"}):
            result = run_local_dialogue(
                config=self.cfg, scenario_id="screen-understanding", sender=sender,
            )
        self.assertEqual(result["safety"]["openai_api_calls"], 0)
        for _, payload, _, _ in sender.calls:
            self.assertNotIn("DO-NOT-TRANSMIT", str(payload))

    def test_refuses_same_model_for_both_roles(self):
        with self.assertRaisesRegex(MentorBridgeError, "distinct model"):
            LocalBridgeConfig("qwen3.5:9b", "qwen3.5:9b")

    def test_requires_known_synthetic_fixture_before_network(self):
        sender = LocalOllamaStub()
        with self.assertRaisesRegex(MentorBridgeError, "unknown synthetic"):
            run_local_dialogue(
                config=self.cfg, scenario_id="private-file", sender=sender,
            )
        self.assertFalse(sender.calls)

    def test_does_not_accept_model_tool_call(self):
        def sender(url, payload, headers, timeout):
            return {"model": payload["model"], "done": True, "message": {
                "content": "Can I run shell?", "tool_calls": [{"name": "shell"}],
            }}
        with self.assertRaisesRegex(MentorBridgeError, "tool"):
            run_local_dialogue(
                config=self.cfg, scenario_id="service-failure", sender=sender,
            )

    def test_incomplete_or_wrong_model_response_fails(self):
        for bad in (
            {"done": False, "message": {"content": "unfinished"}},
            {"model": "not-requested", "message": {"content": "answer"}},
            {"model": "qwen3.5:9b", "message": {"content": ""}},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(MentorBridgeError):
                    run_local_dialogue(
                        config=self.cfg, scenario_id="service-failure",
                        sender=lambda url, payload, headers, timeout: bad,
                    )

    def test_cli_preview_runs_without_models_or_idle_confirmation(self):
        with patch("sofia.mentor.__main__.run_local_dialogue",
                   side_effect=AssertionError("must not invoke model")):
            output = StringIO()
            with redirect_stdout(output):
                code = main([
                    "local-converse", "--scenario", "service-failure",
                    "--student-model", "qwen3.5:9b",
                    "--mentor-model", "qwen3:14b", "--preview",
                ])
        self.assertEqual(code, 0)
        self.assertIn("local-preview-no-network", output.getvalue())
        self.assertIn("ECONNREFUSED", output.getvalue())

    def test_cli_requires_explicit_idle_confirmation_before_model(self):
        with patch("sofia.mentor.__main__.run_local_dialogue",
                   side_effect=AssertionError("must not invoke model")):
            result = main([
                "local-converse", "--scenario", "service-failure",
                "--student-model", "qwen3.5:9b", "--mentor-model", "qwen3:14b",
            ])
        self.assertEqual(result, 2)

    def test_cli_owner_confirmed_idle_invokes_only_local_dialogue(self):
        fake = {"schema": "sofia.mentor.local-dialogue.v1", "events": []}
        with patch("sofia.mentor.__main__.run_local_dialogue", return_value=fake) as execute:
            out = StringIO()
            with redirect_stdout(out):
                status = main([
                    "local-converse", "--scenario", "service-failure",
                    "--student-model", "qwen3.5:9b",
                    "--mentor-model", "qwen3:14b", "--rounds", "1",
                    "--confirm-idle",
                ])
        self.assertEqual(status, 0)
        self.assertEqual(execute.call_count, 1)
        self.assertIn("local-dialogue", out.getvalue())


if __name__ == "__main__":
    import unittest
    unittest.main()
