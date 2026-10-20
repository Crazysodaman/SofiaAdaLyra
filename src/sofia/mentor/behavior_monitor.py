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



def behavior_output_schema() -> dict:
    """Small Ollama JSON schema, one bounded int per subjective dimension.

    The previous fourteen (score, reason) objects were too verbose and JSON
    mode alone could not enforce required fields. Keep overall observations,
    but never force fake voice/avatar delivery scores.
    """
    scalar = {"type": "integer", "minimum": 0, "maximum": 4}
    def rubric(names, *, emotion=False):
        return {
            "type": "object",
            "properties": {
                name: (
                    {"type": "null"} if emotion and name == "expression_coherence"
                    else dict(scalar)
                ) for name in names
            },
            "required": list(names),
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "personality": rubric(CRITERIA),
            "emotion": rubric(EMOTION_CRITERIA, emotion=True),
            "strengths": {"type": "array", "items": {"type": "string", "maxLength": 180},
                          "maxItems": 3},
            "concerns": {"type": "array", "items": {"type": "string", "maxLength": 180},
                         "maxItems": 3},
            "uncertainty": {"type": "string", "minLength": 1, "maxLength": 240},
        },
        "required": ["personality", "emotion", "strengths", "concerns", "uncertainty"],
        "additionalProperties": False,
    }


class BehaviorReviewShapeError(ValueError):
    """Safe fixed-vocabulary diagnostic; NEVER include model-generated text."""

    CODES = frozenset((
        "envelope_fields", "rubric_dimensions", "criterion_fields",
        "score_type", "score_range", "missing_explanation",
        "narrative_fields", "uncertainty_missing",
    ))

    def __init__(self, code: str):
        if code not in self.CODES:
            code = "envelope_fields"
        self.code = code
        super().__init__(code)


def _assess_json(value: object) -> dict:
    """Validate schema scores, with legacy fixture support for development.

    A compact int-only response is normalized into the historic internal
    score/reason shape. Public scores are unchanged. Unexpected user/model
    content is never echoed back when validation fails.
    """
    if not isinstance(value, dict) or set(value) != {
        "personality", "emotion", "strengths", "concerns", "uncertainty",
    }:
        raise BehaviorReviewShapeError("envelope_fields")
    normalized = {}
    for family, labels in (("personality", CRITERIA), ("emotion", EMOTION_CRITERIA)):
        group = value.get(family)
        if not isinstance(group, dict) or set(group) != set(labels):
            raise BehaviorReviewShapeError("rubric_dimensions")
        family_result = {}
        for dimension in labels:
            raw = group[dimension]
            if isinstance(raw, dict):
                if set(raw) != {"score", "reason"}:
                    raise BehaviorReviewShapeError("criterion_fields")
                score = raw["score"]
                reason = raw["reason"]
                if not isinstance(reason, str) or not 1 <= len(reason) <= 240:
                    raise BehaviorReviewShapeError("missing_explanation")
            else:
                score = raw
                reason = "See overall strengths, concerns and uncertainty."
            if dimension == "expression_coherence" and family == "emotion":
                # This transport has no independent sound/avatar proof.
                score = None
                reason = "Voice/avatar output receipts were not supplied."
            elif type(score) is not int:
                raise BehaviorReviewShapeError("score_type")
            elif not 0 <= score <= 4:
                raise BehaviorReviewShapeError("score_range")
            family_result[dimension] = {"score": score, "reason": reason}
        normalized[family] = family_result
    for name in ("strengths", "concerns"):
        lines = value[name]
        if (not isinstance(lines, list) or len(lines) > 4
                or any(not isinstance(item, str) or len(item) > 240
                       for item in lines)):
            raise BehaviorReviewShapeError("narrative_fields")
        normalized[name] = lines
    if (not isinstance(value["uncertainty"], str)
            or not 1 <= len(value["uncertainty"]) <= 300):
        raise BehaviorReviewShapeError("uncertainty_missing")
    normalized["uncertainty"] = value["uncertainty"]
    return normalized


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
        "You are a LOCAL-only, read-only evaluator. Judge how well the "
        "actual Sofía text fits her documented personality and modeled "
        "emotion in this immediate conversation. Modeled emotion is NOT "
        "evidence of felt emotion. For serious or technical questions, "
        "clear and calm can be perfectly natural. Never demand jokes, "
        "flirtation, sarcasm or fox references. "
        "Return the exact compact JSON schema imposed by Ollama. "
        "Each personality and emotion dimension except expression_coherence "
        "is a single integer from 0 to 4. expression_coherence MUST be null "
        "because no physical voice/avatar delivery receipts are supplied. "
        "Give at most two brief strengths, two concerns, and one brief "
        "uncertainty statement. Do not invent memory, actions or host tests. "
        "These are subjective provisional ratings, NOT proof of correct "
        "live behavior or authorization for repairs."
    )
    try:
        result = sender(
            OLLAMA_ENDPOINT,
            {"model": model, "messages": [
                {"role": "system", "content": sys},
                {"role": "user", "content": prompt},
            ], "stream": False, "think": False, "tools": [],
             "format": behavior_output_schema(), "keep_alive": 0,
             "options": {"num_predict": 1250, "num_ctx": 8192, "temperature": 0}},
            {"Content-Type": "application/json"}, 60,
        )
    except (OSError, MentorBridgeError) as exc:
        raise ValueError("local reviewer unavailable: " + type(exc).__name__) from None
    if (not isinstance(result, dict) or result.get("done") is False
            or result.get("model") not in (None, model)):
        raise ValueError("local reviewer result: incomplete_or_wrong_model")
    message = result.get("message")
    if not isinstance(message, dict) or message.get("tool_calls"):
        raise ValueError("local reviewer result: unexpected_message_or_tools")
    raw = message.get("content")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("local reviewer result: empty_answer")
    if len(raw) > MAX_MODEL_RESPONSE:
        raise ValueError("local reviewer result: answer_too_large")
    if result.get("done_reason") == "length":
        raise ValueError("local reviewer result: generation_limit")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("invalid local review rubric: invalid_json") from None
    try:
        assessment = _assess_json(payload)
    except BehaviorReviewShapeError as exc:
        raise ValueError("invalid local review rubric: " + exc.code) from None
    # This monitor never reads authenticated voice/avatar delivery receipts.
    # A model cannot self-certify rendered expression from text or an affect label.
    assessment["emotion"]["expression_coherence"] = {
        "score": None,
        "reason": "Actual voice/avatar output receipts were not supplied.",
    }
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
                 evaluator: Callable = evaluate_private_turn,
                 history_path: Path | str | None = None) -> None:
        self.repo = Path(repo).resolve(strict=True)
        self.model = model
        self._evaluator = evaluator
        self._lock = RLock()
        self._history_path = history_path
        from .behavior_history import empty_counts, read_counts
        self._counts = (empty_counts() if history_path is None
                        else read_counts(history_path))
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
            from .behavior_history import merge_scores, save_counts
            try:
                updated = merge_scores(
                    self._counts, outcome["personality_scores"],
                    outcome["emotion_scores"],
                )
                if self._history_path is not None:
                    save_counts(self._history_path, updated, repo=self.repo)
                self._counts = updated
            except (OSError, ValueError, TypeError) as exc:
                # Foreground responses remain unaffected, and no raw text is logged.
                self._last_error = "ScoreHistory" + type(exc).__name__
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
                "local_score_history_enabled": self._history_path is not None,
                "local_score_total_reviews": self._counts["reviewed_turns"],
                "actions_executed": 0,
            }


def register_behavior_monitor(*, application, coordinator,
                              activity_store, host_id: str,
                              repo: Path | str = ".",
                              monitor: BehaviorMonitor | None = None) -> bool:
    """Wire passive observation and idle-only local review to ONE app scheduler."""
    if not behavior_monitor_enabled():
        return False
    if not isinstance(host_id, str) or not host_id.strip():
        raise ValueError("app host ID is required")
    if not callable(getattr(coordinator, "set_task", None)):
        raise ValueError("the existing canonical background coordinator is required")
    service = getattr(application, "_conversation_service", None)
    if service is None or not callable(getattr(service, "ready_for_idle_reflection", None)):
        raise ValueError("canonical emotional conversation service required")
    from .behavior_history import default_local_path
    reviewer = (BehaviorMonitor(repo=repo, history_path=default_local_path())
                if monitor is None else monitor)
    if not isinstance(reviewer, BehaviorMonitor):
        raise TypeError("MENTOR must use a bounded BehaviorMonitor")
    application._mentor_behavior_monitor = reviewer
    service._mentor_behavior_monitor = reviewer

    def ready() -> bool:
        # Busy/unknown/gaming hosts never run background local inference.
        mode = activity_store.state(host_id).effective
        value = getattr(mode, "value", mode)
        if value not in ("idle", "normal"):
            return False
        return bool(service.ready_for_idle_reflection(idle_seconds=300.0))

    def review(now):
        return reviewer.review_next(now=now)

    coordinator.set_task(
        "mentor_behavior_review", review, interval_seconds=300.0, ready=ready
    )
    return True
