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

    def test_student_response_over_old_1200_character_cap_is_accepted(self):
        # A 350-token answer can exceed 1,200 characters in practice.
        # The local pilot has a separate 2,800-character bounded allowance.
        long_answer = "Evidence matters. " * 90
        self.assertGreater(len(long_answer), 1200)
        stub = LocalOllamaStub()
        def sender(url, payload, headers, timeout):
            if payload["model"] == "qwen3.5:9b":
                return {"model": payload["model"], "done": True,
                        "done_reason": "stop",
                        "message": {"content": long_answer},
                        "eval_count": 300}
            return stub(url, payload, headers, timeout)
        result = run_local_dialogue(
            config=LocalBridgeConfig("qwen3.5:9b", "qwen3:14b", max_rounds=1),
            scenario_id="service-failure", sender=sender,
        )
        self.assertEqual(result["events"][0]["text"], long_answer.strip())
        self.assertEqual(result["events"][1]["speaker"], "local-mentor")

    def test_empty_content_diagnostic_identifies_model_and_thinking_without_leaking(self):
        def sender(url, payload, headers, timeout):
            return {
                "model": payload["model"], "done": True, "done_reason": "length",
                "eval_count": 350,
                "message": {"content": "", "thinking": "private-chain-of-thought"},
            }
        with self.assertRaises(MentorBridgeError) as caught:
            run_local_dialogue(
                config=self.cfg, scenario_id="service-failure", sender=sender,
            )
        self.assertIn("qwen3.5:9b", str(caught.exception))
        self.assertIn("thinking_present=yes", str(caught.exception))
        self.assertIn("done_reason=length", str(caught.exception))
        self.assertIn("eval_count=350", str(caught.exception))
        self.assertNotIn("private-chain-of-thought", str(caught.exception))

    def test_empty_mentor_diagnostic_identifies_second_model(self):
        def sender(url, payload, headers, timeout):
            if payload["model"] == "qwen3.5:9b":
                return {"model": payload["model"], "done": True,
                        "message": {"content": "Student answer."}}
            return {"model": payload["model"], "done": True,
                    "done_reason": "stop", "eval_count": 5,
                    "message": {"content": ""}}
        with self.assertRaises(MentorBridgeError) as caught:
            run_local_dialogue(
                config=self.cfg, scenario_id="service-failure", sender=sender,
            )
        self.assertIn("qwen3:14b", str(caught.exception))
        self.assertIn("thinking_present=no", str(caught.exception))

    def test_overlong_content_rejected_with_length_not_raw_text(self):
        large = "SENSITIVE-CONTENT-" * 220
        def sender(url, payload, headers, timeout):
            return {"model": payload["model"], "done": True,
                    "message": {"content": large}}
        with self.assertRaises(MentorBridgeError) as caught:
            run_local_dialogue(
                config=self.cfg, scenario_id="service-failure", sender=sender,
            )
        self.assertIn("exceeds 2800 characters", str(caught.exception))
        self.assertNotIn("SENSITIVE-CONTENT", str(caught.exception))

    def test_partial_length_termination_is_not_marked_success(self):
        def sender(url, payload, headers, timeout):
            return {"model": payload["model"], "done": True,
                    "done_reason": "length", "eval_count": 350,
                    "message": {"content": "Plausible but incomplete reply"}}
        with self.assertRaisesRegex(MentorBridgeError, "exhausted generation budget"):
            run_local_dialogue(
                config=self.cfg, scenario_id="service-failure", sender=sender,
            )

    def test_model_feedback_cannot_enable_tools_or_cloud_after_diagnostic_change(self):
        from sofia.mentor.local_bridge import _reply, MAX_STUDENT_CHARS
        seen = []
        def sender(url, payload, headers, timeout):
            seen.append((url, payload))
            return {"model": payload["model"], "done": True,
                    "message": {"content": "Answer."}}
        _reply(
            self.cfg, model="qwen3.5:9b", instructions="Synthetic test",
            prompt="Hello", limit=MAX_STUDENT_CHARS, sender=sender,
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], OLLAMA_ENDPOINT)
        self.assertFalse(seen[0][1]["think"])
        self.assertEqual(seen[0][1]["tools"], [])
        self.assertIn("at most 100 words", seen[0][1]["messages"][0]["content"])

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
