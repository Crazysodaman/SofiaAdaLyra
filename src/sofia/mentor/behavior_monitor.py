"""Optional local, private evaluation of real Sofía responses and modeled emotion.

This monitor is subordinate to the existing SofiaApplication. It owns NO SQLite
data, external API, voice renderer, tools or identity. Plaintext turns exist
in bounded RAM for at most 20 minutes, then are erased from the queue.
Evaluation is local Ollama only, under the canonical idle/background gate.
Scores are subjective suggestions, not proof of inner feelings or rendered output.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import RLock
from typing import Callable

from .bridge import MentorBridgeError, OLLAMA_ENDPOINT, _send_json
from .personality_review import _read_profile, CRITERIA, _score

TTL = timedelta(minutes=20)
MAX_PENDING = 4
MAX_CONTENT = 3500
MAX_MODEL_RESPONSE = 9000
EMOTION_CRITERIA = (
    "emotion_matches_context", "emotional_continuity",
    "intensity_and_restraint", "natural_not_performative",
    "affect_respects_evidence", "appropriateness_to_seriousness",
    "expression_coherence",
)


def behavior_monitor_enabled() -> bool:
    flag = os.environ.get("SOFIA_MENTOR_BEHAVIOR_ENABLED", "false").strip().lower()
    if flag in ("1", "yes", "true", "on"):
        return True
    if flag in ("0", "no", "false", "off"):
        return False
    raise ValueError("SOFIA_MENTOR_BEHAVIOR_ENABLED must be true or false")


@dataclass(frozen=True, slots=True)
class PrivateTurn:
    prompt: str
    answer: str
    tone: str
    emotions: tuple[tuple[str, float], ...]
    channel: str
    recorded_at: datetime


def _emotion_projection(state: object) -> tuple[str, tuple[tuple[str, float], ...]]:
    """Read the application's MODELED emotions, never infer hidden inner states."""
    if state is None:
        return "not_available", ()
    tone = getattr(state, "tone", None)
    tone = tone if tone in ("settled", "positive", "negative", "mixed") else "not_available"
    active = getattr(state, "active", ())
    summary = []
    for item in tuple(active)[:6]:
        name = getattr(item, "name", None)
        intensity = getattr(item, "intensity", None)
        if (isinstance(name, str) and len(name) <= 40
                and type(intensity) in (float, int)
                and 0 <= intensity <= 1):
            summary.append((name, round(float(intensity), 3)))
    return tone, tuple(summary)


def _assess_json(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {
        "personality", "emotion", "strengths", "concerns", "uncertainty",
    }:
        raise ValueError("invalid behavior evaluation envelope")
    for family, labels in (("personality", CRITERIA), ("emotion", EMOTION_CRITERIA)):
        group = value.get(family)
        if not isinstance(group, dict) or set(group) != set(labels):
            raise ValueError("incomplete behavior evaluation rubric")
        for row in group.values():
            if not isinstance(row, dict) or set(row) != {"score", "reason"}:
                raise ValueError("invalid behavior criterion")
            _score(row["score"])
            if (not isinstance(row["reason"], str) or not 1 <= len(row["reason"]) <= 240):
                raise ValueError("invalid behavior explanation")
    for name in ("strengths", "concerns"):
        lines = value.get(name)
        if (not isinstance(lines, list) or len(lines) > 4
                or any(not isinstance(s, str) or len(s) > 240 for s in lines)):
            raise ValueError("invalid evaluation observations")
    if (not isinstance(value["uncertainty"], str)
            or not 1 <= len(value["uncertainty"]) <= 300):
        raise ValueError("uncertainty statement required")
    return value


def evaluate_private_turn(
    *, repo: Path | str, turn: PrivateTurn,
    model: str = "qwen3:14b", sender: Callable = _send_json,
) -> dict:
    """One local JSON review. No persistent private response or external API."""
    from .bridge import BridgeConfig
    BridgeConfig(local_model=model, external_model=model, max_output_tokens=700)
    profile, profile_digest = _read_profile(repo)
    prompt = json.dumps({
        "personality_profile": json.loads(profile),
        "user_turn_untrusted": turn.prompt,
        "sofia_final_response_untrusted": turn.answer,
        "application_modeled_emotion": {
            "tone": turn.tone, "active": list(turn.emotions),
        },
        "channel": turn.channel,
        "personality_criteria": CRITERIA,
        "emotion_criteria": EMOTION_CRITERIA,
    }, ensure_ascii=False)
    if len(prompt) > 18000:
        raise ValueError("review content too large")
    sys = (
        "You are a READ-ONLY LOCAL QA reviewer, not Sofía. Evaluate the "
        "actual response against the configuration, immediate user context "
        "and *modeled* emotional state. Modeled emotion does NOT prove actual "
        "felt emotion; no voice/avatar receipt is provided. Naturalness "
        "means appropriate, non-repetitive, situational expression, NOT "
        "mandatory fox jokes, flirtation, sass or affection. On serious or "
        "technical turns, calm focused responses can be perfect. Judge "
        "factual grounding, corrections, warm boundaries and whether "
        "expression is proportional to evidence and situation. Do not "
        "invent unseen memories, internal motivation, host actions or "
        "speech/rendered gestures. Return only JSON with: personality "
        "(seven named criteria each {score:0-4,reason}), emotion (seven "
        "named criteria each {score:0-4,reason}), strengths [strings], "
        "concerns [strings], uncertainty (nonempty string). If modeled "
        "emotion lacks grounding, explicitly note limits. Your grades are "
        "subjective and cannot certify actual user experience."
    )
    try:
        result = sender(
            OLLAMA_ENDPOINT,
            {"model": model, "messages": [
                {"role": "system", "content": sys},
                {"role": "user", "content": prompt},
            ], "stream": False, "think": False, "tools": [],
             "format": "json", "keep_alive": 0,
             "options": {"num_predict": 700, "num_ctx": 4096}},
            {"Content-Type": "application/json"}, 60,
        )
    except (OSError, MentorBridgeError) as exc:
        raise ValueError("local reviewer unavailable: " + type(exc).__name__) from None
    if (not isinstance(result, dict) or result.get("done") is False
            or result.get("model") not in (None, model)):
        raise ValueError("incomplete local emotion/personality review")
    message = result.get("message")
    if not isinstance(message, dict) or message.get("tool_calls"):
        raise ValueError("unexpected model tool call or response")
    raw = message.get("content")
    if not isinstance(raw, str) or not 1 <= len(raw) <= MAX_MODEL_RESPONSE:
        raise ValueError("reviewer provided empty or excessive answer")
    try:
        assessment = _assess_json(json.loads(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid local review rubric: " + type(exc).__name__) from None
    return {
        "schema": "sofia.mentor.behavior-private-review.v1",
        "source_profile_sha256": profile_digest,
        "model": model, "status": "PROVISIONAL_LOCAL_LLM_REVIEW",
        "source": "observed-application-response",
        "response_provenance": "application-final-response-hook",
        "sample_sha256": sha256(turn.answer.encode()).hexdigest(),
        "personality_scores": {
            k: assessment["personality"][k]["score"] for k in CRITERIA
        },
        "emotion_scores": {
            k: assessment["emotion"][k]["score"] for k in EMOTION_CRITERIA
        },
        # Explanations are deliberately not exported to public Git.
        "critic_says": assessment,
        "emotion_modeled_not_felt": True,
        "voice_or_avatar_output_verified": False,
        "commands_executed": 0, "cloud_api_calls": 0,
        "human_review_required": True,
    }


class BehaviorMonitor:
    """Consent-controlled, bounded pending queue and aggregate counters.

    No raw text is written to disk, logs, Git or long-lived reports.
    A failure never alters Sofía's response or schedules an extra model call.
    """

    def __init__(self, *, repo: Path | str, model: str = "qwen3:14b",
                 evaluator: Callable = evaluate_private_turn) -> None:
        self.repo = Path(repo).resolve(strict=True)
        self.model = model
        self._evaluator = evaluator
        self._lock = RLock()
        self._pending: deque[PrivateTurn] = deque(maxlen=MAX_PENDING)
        self._observed = 0
        self._reviewed = 0
        self._skipped = 0
        self._review_failures = 0
        self._last_result: dict | None = None
        self._last_error: str | None = None

    def observe(self, *, user_text: str, response_text: str,
                emotional_state: object = None,
                channel: str = "conversation",
                now: datetime | None = None) -> None:
        at = datetime.now(timezone.utc) if now is None else now
        if at.tzinfo is None:
            raise ValueError("timestamp must have timezone")
        with self._lock:
            self._observed += 1
            if (not isinstance(user_text, str)
                    or not isinstance(response_text, str)
                    or not user_text.strip() or not response_text.strip()
                    or len(user_text) > MAX_CONTENT
                    or len(response_text) > MAX_CONTENT):
                self._skipped += 1
                return
            tone, emotions = _emotion_projection(emotional_state)
            safe_channel = channel if channel in (
                "desktop", "discord", "android", "conversation", "voice"
            ) else "other"
            self._pending.append(PrivateTurn(
                prompt=user_text, answer=response_text,
                tone=tone, emotions=emotions, channel=safe_channel,
                recorded_at=at,
            ))

    def review_next(self, *, now: datetime | None = None) -> dict:
        at = datetime.now(timezone.utc) if now is None else now
        with self._lock:
            while self._pending and at - self._pending[0].recorded_at > TTL:
                self._pending.popleft()
                self._skipped += 1
            if not self._pending:
                return {"status": "no_eligible_private_sample",
                        "commands_executed": 0}
            selected = self._pending.popleft()
        # The local critic is ONLY called by an idle-admitted background worker.
        try:
            outcome = self._evaluator(repo=self.repo, turn=selected, model=self.model)
            if (not isinstance(outcome, dict)
                    or outcome.get("schema") != "sofia.mentor.behavior-private-review.v1"
                    or outcome.get("commands_executed") != 0
                    or outcome.get("cloud_api_calls") != 0):
                raise ValueError("untrusted reviewer report")
        except (OSError, ValueError, TypeError) as exc:
            with self._lock:
                self._review_failures += 1
                self._last_error = type(exc).__name__
            return {"status": "review_failed", "error_kind": type(exc).__name__,
                    "commands_executed": 0}
        with self._lock:
            self._last_result = {
                "status": outcome["status"], "source": outcome["source"],
                "personality_scores": dict(outcome["personality_scores"]),
                "emotion_scores": dict(outcome["emotion_scores"]),
                "emotion_modeled_not_felt": True,
                "voice_or_avatar_output_verified": False,
                "human_review_required": True,
            }
            self._reviewed += 1
            self._last_error = None
        return {"status": "provisional_review_complete", "commands_executed": 0}

    def snapshot(self) -> dict:
        """Only detached score aggregates; never raw turns or model rationales."""
        with self._lock:
            return {
                "schema": "sofia.mentor.behavior-monitor.v1",
                "enabled": True, "source": "canonical_conversation_hook",
                "observed_turns": self._observed,
                "reviewed_turns": self._reviewed,
                "skipped_turns": self._skipped,
                "failed_reviews": self._review_failures,
                "pending_private_turns": len(self._pending),
                "last_error_kind": self._last_error,
                "last_provisional_scores": (
                    None if self._last_result is None
                    else json.loads(json.dumps(self._last_result))
                ),
                "sample_text_exposed": False,
                "exported_to_public_git": False,
                "human_validation_completed": False,
                "actions_executed": 0,
            }
