"""Read-only Git MENTOR inbox consumer for SofiaApplication.

Only one fixed PUBLIC GitHub raw path is fetched. No credentials, file uploads,
model calls, raw chats, screenshots, shell commands, SQLite, Git writes, or
automatic learning. External feedback is explicitly *advisory-only*.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from threading import RLock
from typing import Callable
from urllib import error, request

from .exchange import MAX_REVIEW_BYTES, MentorExchangeError, validate_advisory_review

PUBLIC_INBOX_URL = (
    "https://raw.githubusercontent.com/Crazysodaman/SofiaAdaLyra/"
    "main/docs/mentor_exchange/inbox/latest.json"
)
MAX_AGE = timedelta(days=14)


class MentorRemoteError(MentorExchangeError):
    """Remote public inbox is unavailable or cannot be trusted as input."""


def _raw_get(*, timeout_seconds: int = 12) -> bytes:
    """Fixed HTTPS endpoint; reject redirects, proxy overrides and huge files."""
    if type(timeout_seconds) is not int or not 3 <= timeout_seconds <= 30:
        raise MentorRemoteError("invalid read-only network timeout")

    class NoRedirects(request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise MentorRemoteError("Git mailbox redirects are forbidden")

    opener = request.build_opener(request.ProxyHandler({}), NoRedirects())
    req = request.Request(
        PUBLIC_INBOX_URL, method="GET",
        headers={"Accept": "application/json", "User-Agent": "Sofia-Mentor-ReadOnly/1"},
    )
    try:
        with opener.open(req, timeout=timeout_seconds) as res:
            if res.geturl() != PUBLIC_INBOX_URL:
                raise MentorRemoteError("unexpected inbox response origin")
            data = res.read(MAX_REVIEW_BYTES + 1)
    except (error.URLError, error.HTTPError, TimeoutError, OSError) as exc:
        # Deliberately do not echo arbitrary HTTP response bodies or URLs.
        raise MentorRemoteError("public review unavailable: " + type(exc).__name__) from None
    if len(data) > MAX_REVIEW_BYTES:
        raise MentorRemoteError("public review exceeds size limit")
    return data


def fetch_public_review(
    *, transport: Callable[..., bytes] = _raw_get,
    now: datetime | None = None,
) -> tuple[dict, str]:
    """Validate schema and staleness, then return detached data and digest."""
    at = datetime.now(timezone.utc) if now is None else now
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise MentorRemoteError("remote poll time must be timezone-aware")
    try:
        payload = transport()
    except MentorRemoteError:
        raise
    except Exception as exc:
        raise MentorRemoteError("remote transport failed: " + type(exc).__name__) from None
    if not isinstance(payload, bytes) or len(payload) > MAX_REVIEW_BYTES:
        raise MentorRemoteError("remote payload is not bounded bytes")
    try:
        data = validate_advisory_review(json.loads(payload))
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise MentorRemoteError("public review failed strict schema validation") from None
    reviewed = datetime.fromisoformat(data["review_created_at"].replace("Z", "+00:00"))
    age = at.astimezone(timezone.utc) - reviewed.astimezone(timezone.utc)
    if age < -timedelta(minutes=10) or age > MAX_AGE:
        raise MentorRemoteError("public review timestamp is stale or future-dated")
    return deepcopy(data), sha256(payload).hexdigest()


class MentorReviewConsumer:
    """Application-owned in-memory projection; no callbacks/actions on advice."""

    def __init__(self, *, fetcher: Callable = fetch_public_review):
        if not callable(fetcher):
            raise TypeError("MENTOR inbox fetcher must be callable")
        self._fetcher = fetcher
        self._lock = RLock()
        self._record: dict | None = None
        self._digest: str | None = None
        self._last_checked: str | None = None
        self._error_kind: str | None = None

    def poll(self, *, now: datetime | None = None) -> dict:
        """Fetch once. Failure does not erase last good review or fabricate work."""
        at = datetime.now(timezone.utc) if now is None else now
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("MENTOR poll requires timezone-aware datetime")
        try:
            review, digest = self._fetcher(now=at)
            validate_advisory_review(review)
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(c not in "0123456789abcdef" for c in digest)):
                raise MentorRemoteError("invalid digest")
        except (MentorExchangeError, OSError, ValueError, TypeError) as exc:
            with self._lock:
                self._error_kind = type(exc).__name__
                self._last_checked = at.isoformat()
            return {"status": "unavailable", "error_kind": type(exc).__name__,
                    "retained_last_good": self._record is not None}
        with self._lock:
            changed = digest != self._digest
            self._digest = digest
            self._record = deepcopy(review)
            self._error_kind = None
            self._last_checked = at.isoformat()
        return {"status": "updated" if changed else "unchanged",
                "reviewed_source_revision": review["reviewed_source_revision"],
                "recommendation_count": len(review["recommendations"]),
                "advisory_only": True, "actions_executed": 0}

    def snapshot(self) -> dict:
        """Detached projection safe to inspect, not to promote to instructions."""
        with self._lock:
            review = deepcopy(self._record)
            return {
                "schema": "sofia.mentor.inbox-snapshot.v1",
                "state": (
                    "available" if review is not None and self._error_kind is None
                    else "last-known" if review is not None else "unavailable"
                ),
                "last_checked": self._last_checked,
                "error_kind": self._error_kind,
                "source": "public-github-untrusted",
                "advisory_only": True, "actions_executed": 0,
                "trusted_owner_instruction": False,
                "review": review,
            }
