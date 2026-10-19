"""End-to-end read-only Git inbox consumption with no API or host commands."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from sofia.mentor.__main__ import main
from sofia.mentor.exchange import MentorExchangeError
from sofia.mentor.remote_inbox import (
    MAX_REVIEW_BYTES, MentorRemoteError, MentorReviewConsumer,
    PUBLIC_INBOX_URL, _raw_get, fetch_public_review,
    mentor_git_enabled, register_application_review_task,
)


NOW = datetime(2026, 10, 19, 23, 45, tzinfo=timezone.utc)


def review():
    return {
        "schema": "sofia.mentor.advisory-review.v1",
        "visibility": "public",
        "reviewed_source_revision": "a" * 40,
        "review_created_at": NOW.isoformat(),
        "reviewer": "chatgpt-mentor",
        "summary": "Investigate the synthetic listener without claiming a real failure.",
        "recommendations": [{
            "id": "REV-001", "task_ids": [],
            "severity": "needs-verification", "action": "run-safe-test",
            "observation": "The demonstration has no real host proof.",
            "suggested_check": "Run an independent synthetic control.",
            "acceptance": "Record real results tied to a Git revision.",
            "requires_owner_approval": True,
        }],
        "limitations": ["Text data only; no trusted instructions."],
    }


class TestRemoteInbox(TestCase):
    def test_fetch_bound_public_json_and_immutable_source_identity(self):
        payload = json.dumps(review()).encode()
        doc, digest = fetch_public_review(
            transport=lambda: payload, now=NOW,
        )
        self.assertEqual(doc["reviewer"], "chatgpt-mentor")
        self.assertEqual(len(digest), 64)
        doc["recommendations"][0]["action"] = "mutated"
        again, same_digest = fetch_public_review(
            transport=lambda: payload, now=NOW,
        )
        self.assertEqual(again["recommendations"][0]["action"], "run-safe-test")
        self.assertEqual(digest, same_digest)

    def test_stale_future_or_oversized_advice_is_refused(self):
        payload = json.dumps(review()).encode()
        for now in (NOW + timedelta(days=15), NOW - timedelta(hours=1)):
            with self.subTest(now=now), self.assertRaisesRegex(
                MentorRemoteError, "stale or future"
            ):
                fetch_public_review(transport=lambda: payload, now=now)
        with self.assertRaisesRegex(MentorRemoteError, "bounded bytes"):
            fetch_public_review(
                transport=lambda: b"x" * (MAX_REVIEW_BYTES + 1),
                now=NOW,
            )

    def test_unknown_fields_and_implied_authority_are_refused(self):
        packet = review()
        packet["recommendations"][0]["requires_owner_approval"] = False
        with self.assertRaisesRegex(MentorRemoteError, "strict schema"):
            fetch_public_review(
                transport=lambda: json.dumps(packet).encode(), now=NOW,
            )
        packet = review()
        packet["execute"] = "powershell"
        with self.assertRaises(MentorRemoteError):
            fetch_public_review(
                transport=lambda: json.dumps(packet).encode(), now=NOW,
            )

    def test_network_error_does_not_discard_last_good_snapshot(self):
        events = []
        def fetcher(*, now):
            events.append(now)
            if len(events) > 1:
                raise MentorRemoteError("offline")
            return review(), "a" * 64
        consumer = MentorReviewConsumer(fetcher=fetcher)
        first = consumer.poll(now=NOW)
        self.assertEqual(first["status"], "updated")
        snapshot = consumer.snapshot()
        self.assertEqual(snapshot["state"], "available")
        snapshot["review"]["summary"] = "Tampered with local copy"
        self.assertNotEqual(
            consumer.snapshot()["review"]["summary"], "Tampered with local copy"
        )
        failure = consumer.poll(now=NOW + timedelta(hours=1))
        self.assertEqual(failure["status"], "unavailable")
        self.assertTrue(failure["retained_last_good"])
        self.assertEqual(consumer.snapshot()["state"], "last-known")
        self.assertEqual(consumer.snapshot()["actions_executed"], 0)

    def test_unchanged_review_does_not_fabricate_new_work(self):
        consumer = MentorReviewConsumer(
            fetcher=lambda *, now: (review(), "a" * 64)
        )
        self.assertEqual(consumer.poll(now=NOW)["status"], "updated")
        second = consumer.poll(now=NOW + timedelta(hours=1))
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["actions_executed"], 0)

    def test_opt_in_off_by_default_and_invalid_flag_denied(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(mentor_git_enabled())
        with patch.dict("os.environ", {"SOFIA_MENTOR_GIT_ENABLED": "1"}):
            self.assertTrue(mentor_git_enabled())
        with patch.dict("os.environ", {"SOFIA_MENTOR_GIT_ENABLED": "maybe"}):
            with self.assertRaises(MentorRemoteError):
                mentor_git_enabled()

    def test_register_reuses_existing_scheduler_and_blocks_unknown_gaming_busy(self):
        tasks = {}
        coordinator = SimpleNamespace(set_task=lambda name, callback, **kw:
                                      tasks.__setitem__(name, (callback, kw)))
        application = SimpleNamespace(_mentor_review_consumer=None)
        current_activity = SimpleNamespace(effective="unknown")
        activity_store = SimpleNamespace(state=lambda host: current_activity)
        consumer = MentorReviewConsumer(fetcher=lambda *, now: (review(), "b" * 64))
        with patch.dict("os.environ", {"SOFIA_MENTOR_GIT_ENABLED": "1"}):
            self.assertTrue(register_application_review_task(
                application=application, coordinator=coordinator,
                activity_store=activity_store, host_id="test-host",
                consumer=consumer,
            ))
        callback, kwargs = tasks["mentor_git_review"]
        self.assertIs(application._mentor_review_consumer, consumer)
        self.assertEqual(kwargs["interval_seconds"], 3600)
        for mode in (
            "unknown", "gaming", "busy", "do_not_disturb",
        ):
            current_activity.effective = mode
            self.assertFalse(kwargs["ready"]())
        current_activity.effective = "idle"
        self.assertTrue(kwargs["ready"]())
        result = callback(NOW)
        self.assertEqual(result["status"], "updated")
        current_activity.effective = "normal"
        self.assertTrue(kwargs["ready"]())
        self.assertEqual(consumer.snapshot()["review"]["reviewer"], "chatgpt-mentor")

    def test_without_opt_in_nothing_registered_and_no_network(self):
        tasks = []
        application = SimpleNamespace(_mentor_review_consumer=None)
        coordinator = SimpleNamespace(set_task=lambda *args, **kwargs:
                                      tasks.append(args))
        with patch.dict("os.environ", {}, clear=True):
            result = register_application_review_task(
                application=application, coordinator=coordinator,
                activity_store=None, host_id="test-host",
            )
        self.assertFalse(result)
        self.assertFalse(tasks)
        self.assertIsNone(application._mentor_review_consumer)

    def test_cli_public_network_requires_explicit_opt_in(self):
        with patch("sofia.mentor.__main__.MentorReviewConsumer",
                   side_effect=AssertionError("must not fetch")):
            self.assertEqual(main(["exchange-poll"]), 2)
        sample = MentorReviewConsumer(fetcher=lambda *, now: (review(), "a" * 64))
        with patch("sofia.mentor.__main__.MentorReviewConsumer", return_value=sample):
            output = StringIO()
            with redirect_stdout(output):
                status = main(["exchange-poll", "--allow-public-network"])
        self.assertEqual(status, 0)
        self.assertIn("advisory_only", output.getvalue())
        self.assertNotIn("OPENAI_API_KEY", output.getvalue())

    def test_fixed_endpoint_request_has_no_auth_and_refuses_redirect(self):
        class Response:
            def __init__(self, data):
                self.data = data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return PUBLIC_INBOX_URL
            def read(self, limit):
                return self.data[:limit]
        calls = []
        class Opener:
            def open(self, req, timeout):
                calls.append((req, timeout))
                return Response(json.dumps(review()).encode())
        with patch("sofia.mentor.remote_inbox.request.build_opener",
                   return_value=Opener()):
            raw = _raw_get()
        self.assertTrue(raw)
        self.assertEqual(len(calls), 1)
        request, timeout = calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, PUBLIC_INBOX_URL)
        self.assertIsNone(request.data)
        self.assertFalse(request.has_header("Authorization"))


if __name__ == "__main__":
    import unittest
    unittest.main()
